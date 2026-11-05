"""Work out who needs which alert, schedule reminders, and send what is due."""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta

from ..config import Config
from ..db import now_iso
from . import notifier
from .matcher import match_user

log = logging.getLogger(__name__)

NEW_NOTICE = -1                      # offset_days code for "new notice" alerts


def revised_code(version: int) -> int:
    return -(100 + version)          # offset_days code for "notice revised" alerts


def _applies(notice_row) -> dict:
    try:
        return json.loads(notice_row["applies_to_json"] or "{}")
    except json.JSONDecodeError:
        return {}


def _matching_users(conn, notice_row):
    applies = _applies(notice_row)
    for user in conn.execute("SELECT * FROM users").fetchall():
        verdict = match_user(applies, user["course"], user["semester"], user["batch"])
        if verdict != "no":
            yield user, verdict


def _plan_reminders(conn, user_id: int, notice_id: int, deadlines, today: date) -> int:
    created = 0
    for dl in deadlines:
        try:
            due = date.fromisoformat(dl["due_date"])
        except ValueError:
            continue
        for offset in Config.REMINDER_OFFSETS_DAYS:
            remind_on = due - timedelta(days=offset)
            if remind_on < today:
                continue
            cur = conn.execute(
                "INSERT OR IGNORE INTO alerts (user_id, notice_id, deadline_id, offset_days, remind_on) "
                "VALUES (?, ?, ?, ?, ?)", (user_id, notice_id, dl["id"], offset, remind_on.isoformat()))
            created += cur.rowcount
    return created


def schedule_for_notice(conn, notice_id: int, today: date | None = None) -> int:
    """Create reminder rows for every matching student of one notice."""
    today = today or date.today()
    notice = conn.execute("SELECT * FROM notices WHERE id = ?", (notice_id,)).fetchone()
    deadlines = conn.execute("SELECT * FROM deadlines WHERE notice_id = ? AND due_date >= ?",
                             (notice_id, today.isoformat())).fetchall()
    created = 0
    for user, _verdict in _matching_users(conn, notice):
        created += _plan_reminders(conn, user["id"], notice_id, deadlines, today)
    return created


def schedule_for_user(conn, user_id: int, today: date | None = None) -> int:
    """When a student signs up, give them reminders for notices that already exist."""
    today = today or date.today()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    created = 0
    for notice in conn.execute("SELECT * FROM notices").fetchall():
        if match_user(_applies(notice), user["course"], user["semester"], user["batch"]) == "no":
            continue
        deadlines = conn.execute("SELECT * FROM deadlines WHERE notice_id = ? AND due_date >= ?",
                                 (notice["id"], today.isoformat())).fetchall()
        created += _plan_reminders(conn, user_id, notice["id"], deadlines, today)
    return created


def _link(notice) -> str:
    return notice["url"] if notice["url"] and not str(notice["url"]).startswith("local://") else "(see the app)"


def send_notice_alerts(conn, notice_id: int, kind: str, change_summary: str = "") -> int:
    """Immediately tell matching students about a NEW or REVISED notice (once each)."""
    notice = conn.execute("SELECT * FROM notices WHERE id = ?", (notice_id,)).fetchone()
    code = NEW_NOTICE if kind == "new" else revised_code(notice["version"])
    deadlines = conn.execute("SELECT * FROM deadlines WHERE notice_id = ? ORDER BY due_date",
                             (notice_id,)).fetchall()
    lines = [f"{d['label']}: {d['due_date']}" for d in deadlines[:4]]
    sent = 0
    for user, verdict in _matching_users(conn, notice):
        cur = conn.execute(
            "INSERT OR IGNORE INTO alerts (user_id, notice_id, deadline_id, offset_days, remind_on) "
            "VALUES (?, ?, 0, ?, ?)", (user["id"], notice_id, code, date.today().isoformat()))
        if cur.rowcount == 0:
            continue
        alert_id = cur.lastrowid
        head = "New notice" if kind == "new" else "Notice revised"
        maybe = " (may apply to you - please check)" if verdict == "maybe" else ""
        subject = f"{head}: {notice['title']}{maybe}"
        body_parts = [notice["summary"] or ""]
        if change_summary:
            body_parts.append(f"What changed: {change_summary}")
        body_parts += lines
        body_parts += [f"Original notice: {_link(notice)}",
                       "Always confirm on the official notice. Sent by NoticeNest."]
        channel = notifier.deliver(user, subject, "\n".join(p for p in body_parts if p))
        conn.execute("UPDATE alerts SET sent_at = ?, channel = ?, status = ? WHERE id = ?",
                     (now_iso(), channel, "sent" if channel else "failed", alert_id))
        sent += 1 if channel else 0
    return sent


def process_due_alerts(conn, today: date | None = None) -> dict:
    """Send every reminder whose day has come. Skips (and marks) reminders for past deadlines."""
    today = today or date.today()
    stats = {"sent": 0, "failed": 0, "expired": 0}
    rows = conn.execute(
        "SELECT a.id AS alert_id, a.offset_days, u.*, d.label, d.due_date, d.verified, "
        "n.title, n.url, n.review_status FROM alerts a "
        "JOIN users u ON u.id = a.user_id JOIN deadlines d ON d.id = a.deadline_id "
        "JOIN notices n ON n.id = a.notice_id "
        "WHERE a.sent_at IS NULL AND a.status = 'pending' AND a.deadline_id != 0 AND a.remind_on <= ?",
        (today.isoformat(),)).fetchall()
    for row in rows:
        due = date.fromisoformat(row["due_date"])
        days_left = (due - today).days
        if days_left < 0:
            conn.execute("UPDATE alerts SET status = 'expired' WHERE id = ?", (row["alert_id"],))
            stats["expired"] += 1
            continue
        when = "today" if days_left == 0 else "tomorrow" if days_left == 1 else f"in {days_left} days"
        subject = f"Reminder: {row['label']} is {when}"
        warn = "" if row["verified"] else "\nNote: this date could not be double-checked. Please confirm."
        body = (f"{row['title']}\nDate: {due.strftime('%d %b %Y')}{warn}\n"
                f"Original notice: {_link(row)}\n"
                "Always confirm on the official notice. Sent by NoticeNest.")
        channel = notifier.deliver(row, subject, body)
        conn.execute("UPDATE alerts SET sent_at = ?, channel = ?, status = ? WHERE id = ?",
                     (now_iso(), channel, "sent" if channel else "failed", row["alert_id"]))
        stats["sent" if channel else "failed"] += 1
    return stats
