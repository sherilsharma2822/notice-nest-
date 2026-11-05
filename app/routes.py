"""Web pages. Each function below answers one URL."""
from __future__ import annotations

import json
import re
import secrets
from datetime import date, datetime, timedelta

from flask import (Blueprint, Response, abort, flash, redirect, render_template, request,
                   session, url_for)

from .config import Config
from .db import connection, now_iso
from .services import alerts
from .services.matcher import COURSE_CHOICES, match_user, normalize_course

bp = Blueprint("main", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CHAT_ID_RE = re.compile(r"^-?\d{3,20}$")


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def check_csrf() -> None:
    """Block forms that did not come from our own pages."""
    if not request.form.get("csrf") or request.form.get("csrf") != session.get("csrf"):
        abort(400)


def current_user(conn):
    uid = session.get("user_id")
    return conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone() if uid else None


def describe_applies(applies: dict) -> str:
    if applies.get("all"):
        return "Everyone"
    courses, sems = applies.get("courses", []), applies.get("semesters", [])
    if not courses and not sems:
        return "Not stated in the notice"
    parts = []
    if courses:
        parts.append(", ".join(courses))
    if sems:
        parts.append("semester " + " and ".join(str(s) for s in sems) if len(sems) < 3
                     else "semesters " + ", ".join(str(s) for s in sems))
    return " - ".join(parts)


def _loads(text, default):
    try:
        return json.loads(text) if text else default
    except json.JSONDecodeError:
        return default


def load_notices(conn, user, ntype: str = "", show_all: bool = False, notice_id: int | None = None) -> list[dict]:
    """Notices as plain dicts, with deadlines and a yes/maybe/no match for the signed-in student."""
    today = date.today()
    query = ("SELECT n.*, s.name AS source_name FROM notices n JOIN sources s ON s.id = n.source_id "
             + ("WHERE n.id = ? " if notice_id else "")
             + "ORDER BY COALESCE(n.published_date, substr(n.first_seen, 1, 10)) DESC, n.id DESC LIMIT 300")
    rows = conn.execute(query, (notice_id,) if notice_id else ()).fetchall()

    by_notice: dict[int, list[dict]] = {}
    for d in conn.execute("SELECT * FROM deadlines ORDER BY due_date").fetchall():
        by_notice.setdefault(d["notice_id"], []).append(dict(d))

    notices = []
    for row in rows:
        n = dict(row)
        n["applies_to"] = _loads(n["applies_to_json"], {})
        n["applies_text"] = describe_applies(n["applies_to"])
        n["fees"] = _loads(n["fees_json"], [])
        n["issues"] = _loads(n["issues_json"], [])
        n["deadlines"] = by_notice.get(n["id"], [])
        for d in n["deadlines"]:
            d["date"] = date.fromisoformat(d["due_date"])
            d["days_left"] = (d["date"] - today).days
        upcoming = [d for d in n["deadlines"] if d["days_left"] >= 0]
        n["next_due"] = upcoming[0]["date"] if upcoming else None
        n["days_left"] = upcoming[0]["days_left"] if upcoming else None
        n["match"] = (match_user(n["applies_to"], user["course"], user["semester"], user["batch"])
                      if user else None)
        if ntype and n["notice_type"] != ntype:
            continue
        if user and n["match"] == "no" and not show_all and not notice_id:
            continue
        notices.append(n)
    return notices


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
@bp.route("/")
def dashboard():
    ntype = request.args.get("type", "")
    show_all = request.args.get("all") == "1"
    with connection() as conn:
        user = current_user(conn)
        notices = load_notices(conn, user, ntype, show_all)
        total = conn.execute("SELECT COUNT(*) AS c FROM notices").fetchone()["c"]
    horizon = date.today() + timedelta(days=60)
    coming = [{"deadline": d, "notice": n} for n in notices for d in n["deadlines"]
              if 0 <= d["days_left"] and d["date"] <= horizon and n["match"] != "no"]
    coming.sort(key=lambda item: item["deadline"]["date"])
    return render_template("dashboard.html", user=user, notices=notices, coming=coming[:12],
                           ntype=ntype, show_all=show_all, total=total)


@bp.route("/notice/<int:notice_id>")
def notice_page(notice_id: int):
    with connection() as conn:
        user = current_user(conn)
        found = load_notices(conn, user, notice_id=notice_id)
        if not found:
            abort(404)
        changes = conn.execute(
            "SELECT * FROM changes WHERE notice_id = ? OR related_notice_id = ? ORDER BY created_at DESC",
            (notice_id, notice_id)).fetchall()
    return render_template("notice.html", n=found[0], user=user, changes=changes)


@bp.route("/changes")
def changes_page():
    with connection() as conn:
        rows = conn.execute(
            "SELECT c.*, n.title AS title, r.title AS related_title FROM changes c "
            "JOIN notices n ON n.id = c.notice_id LEFT JOIN notices r ON r.id = c.related_notice_id "
            "ORDER BY c.created_at DESC LIMIT 100").fetchall()
    return render_template("changes.html", changes=rows)


@bp.route("/profile", methods=["GET", "POST"])
def profile():
    with connection() as conn:
        user = current_user(conn)
        if request.method == "POST":
            check_csrf()
            form = request.form
            name = form.get("name", "").strip()[:80]
            email = form.get("email", "").strip().lower()[:120]
            course = normalize_course(form.get("course", ""))
            chat_id = form.get("telegram_chat_id", "").strip()[:25]
            batch = form.get("batch", "").strip()[:12]
            try:
                semester = int(form.get("semester", "0"))
            except ValueError:
                semester = 0

            errors = []
            if not name:
                errors.append("Please enter your name.")
            if not EMAIL_RE.match(email):
                errors.append("Please enter a valid email address.")
            if course not in COURSE_CHOICES:
                errors.append("Please choose your course.")
            if not 1 <= semester <= 10:
                errors.append("Semester must be between 1 and 10.")
            if chat_id and not CHAT_ID_RE.match(chat_id):
                errors.append("The Telegram chat ID should be a number (see the setup guide).")
            clash = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if clash and (not user or clash["id"] != user["id"]):
                errors.append("That email already has a profile. Open your private link to edit it.")

            if errors:
                for message in errors:
                    flash(message, "error")
                return render_template("profile.html", user=user, courses=COURSE_CHOICES, form=form), 400

            if user:
                conn.execute("UPDATE users SET name=?, email=?, telegram_chat_id=?, course=?, semester=?, batch=? "
                             "WHERE id=?", (name, email, chat_id or None, course, semester, batch or None, user["id"]))
                user_id = user["id"]
                # Old pending reminders were planned for the old course/semester.
                conn.execute("DELETE FROM alerts WHERE user_id = ? AND sent_at IS NULL", (user_id,))
            else:
                cur = conn.execute(
                    "INSERT INTO users (name, email, token, telegram_chat_id, course, semester, batch, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (name, email, secrets.token_urlsafe(16), chat_id or None, course, semester, batch or None,
                     now_iso()))
                user_id = cur.lastrowid
            session["user_id"] = user_id
            planned = alerts.schedule_for_user(conn, user_id)
            flash(f"Profile saved. {planned} reminders are scheduled for notices already in the system.", "ok")
            return redirect(url_for("main.profile"))
    return render_template("profile.html", user=user, courses=COURSE_CHOICES, form={})


@bp.route("/u/<token>")
def private_link(token: str):
    with connection() as conn:
        row = conn.execute("SELECT id FROM users WHERE token = ?", (token,)).fetchone()
    if not row:
        abort(404)
    session["user_id"] = row["id"]
    return redirect(url_for("main.profile"))


@bp.route("/profile/delete", methods=["POST"])
def profile_delete():
    check_csrf()
    with connection() as conn:
        user = current_user(conn)
        if user:
            conn.execute("DELETE FROM users WHERE id = ?", (user["id"],))
    session.pop("user_id", None)
    flash("Your profile and reminders were deleted.", "ok")
    return redirect(url_for("main.dashboard"))


@bp.route("/calendar.ics")
def calendar():
    with connection() as conn:
        user = current_user(conn)
        if not user:
            abort(404)
        notices = load_notices(conn, user)
    events = [(n, d) for n in notices if n["match"] in ("yes", "maybe") for d in n["deadlines"] if d["days_left"] >= 0]
    return Response(build_ics(events), mimetype="text/calendar",
                    headers={"Content-Disposition": "attachment; filename=noticenest.ics"})


def _ics_escape(text: str) -> str:
    return (text or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def build_ics(events) -> str:
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//NoticeNest//EN", "CALSCALE:GREGORIAN"]
    for notice, d in events:
        end = d["date"] + timedelta(days=1)
        lines += ["BEGIN:VEVENT", f"UID:noticenest-{d['id']}@localhost", f"DTSTAMP:{stamp}",
                  f"DTSTART;VALUE=DATE:{d['date']:%Y%m%d}", f"DTEND;VALUE=DATE:{end:%Y%m%d}",
                  f"SUMMARY:{_ics_escape(d['label'] + ': ' + notice['title'])}",
                  f"DESCRIPTION:{_ics_escape(notice['url'] or '')}", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


@bp.route("/metrics")
def metrics():
    report = None
    if Config.EVAL_RESULTS_FILE.exists():
        try:
            report = json.loads(Config.EVAL_RESULTS_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            report = None
    with connection() as conn:
        stats = {
            "notices": conn.execute("SELECT COUNT(*) c FROM notices").fetchone()["c"],
            "needs_review": conn.execute("SELECT COUNT(*) c FROM notices WHERE review_status='needs_review'").fetchone()["c"],
            "by_mode": {r["extraction_mode"]: r["c"] for r in conn.execute(
                "SELECT extraction_mode, COUNT(*) c FROM notices GROUP BY extraction_mode")},
            "users": conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"],
            "alerts_sent": conn.execute("SELECT COUNT(*) c FROM alerts WHERE status='sent'").fetchone()["c"],
            "llm_cache": conn.execute("SELECT COUNT(*) c FROM llm_cache").fetchone()["c"],
        }
    return render_template("metrics.html", report=report, stats=stats)


@bp.route("/about")
def about():
    return render_template("about.html")


@bp.route("/health")
def health():
    return {"status": "ok"}
