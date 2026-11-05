"""The heart of NoticeNest: fetch -> read -> extract -> validate -> store -> alert.

Read this file top to bottom to understand the whole project.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import logging
import re
from collections import Counter
from datetime import date, datetime, timedelta

import yaml

from ..config import Config
from ..db import connection, now_iso, upsert_source
from . import alerts, ai_extractor, change_detector, fetcher, regex_extractor, text_extractor, validator
from .fetcher import RawNotice
from .llm_client import llm_enabled

log = logging.getLogger(__name__)

REVISION_WORDS = re.compile(r"\b(revised|revision|extended|extension|corrigendum|postponed|rescheduled|"
                            r"amended|amendment|addendum)\b", re.I)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_sources() -> list[dict]:
    data = yaml.safe_load(Config.SOURCES_FILE.read_text(encoding="utf-8")) or {}
    return data.get("sources", [])


# ---------------------------------------------------------------------------
# Step: get the text of a notice
# ---------------------------------------------------------------------------
def get_notice_text(raw: RawNotice) -> str | None:
    """Local notices already carry their text; web notices are downloaded now."""
    if raw.text is not None:
        return text_extractor.clean_text(raw.text)
    if not raw.url:
        return None
    resp = fetcher.polite_get(raw.url)
    if resp is None:
        return None
    if fetcher.looks_like_pdf(resp):
        text, scanned = text_extractor.pdf_to_text(resp.content)
        if scanned:
            log.info("%s looks like a scanned PDF (no readable text).", raw.url)
        return text
    return text_extractor.html_to_text(resp.text)


# ---------------------------------------------------------------------------
# Step: extract + validate
# ---------------------------------------------------------------------------
def extract_and_validate(title: str, text: str, published: str | None):
    """Try the AI first (if switched on), else use regex. Always validate the result."""
    data, mode = None, "regex"
    if text and llm_enabled():
        data = ai_extractor.extract_with_llm(title, text, published)
        if data is not None:
            mode = "llm"
    if data is None:
        data = regex_extractor.extract_all(title, text)
    return validator.validate(data, text, published), mode


# ---------------------------------------------------------------------------
# Step: save to the database
# ---------------------------------------------------------------------------
def _replace_deadlines(conn, notice_id: int, deadlines: list[dict]) -> None:
    conn.execute("DELETE FROM alerts WHERE notice_id = ? AND sent_at IS NULL AND deadline_id != 0", (notice_id,))
    conn.execute("DELETE FROM deadlines WHERE notice_id = ?", (notice_id,))
    for d in deadlines:
        conn.execute("INSERT INTO deadlines (notice_id, label, due_date, snippet, verified) VALUES (?,?,?,?,?)",
                     (notice_id, d["label"], d["date"], d["snippet"], 1 if d["verified"] else 0))


def _notice_columns(result: validator.ValidationResult, mode: str) -> dict:
    data = result.data
    return {
        "notice_type": data["notice_type"], "summary": data["summary"],
        "applies_to_json": json.dumps(data["applies_to"]), "fees_json": json.dumps(data["fees"]),
        "action_required": data["action_required"], "extraction_mode": mode,
        "review_status": result.status, "issues_json": json.dumps(result.issues),
    }


def _stored_deadlines(conn, notice_id: int) -> list[dict]:
    rows = conn.execute("SELECT label, due_date FROM deadlines WHERE notice_id = ?", (notice_id,)).fetchall()
    return [{"label": r["label"], "date": r["due_date"]} for r in rows]


def _handle_new(conn, source_id: int, fingerprint: str, raw: RawNotice, text: str) -> int:
    result, mode = extract_and_validate(raw.title, text, raw.published)
    cols = _notice_columns(result, mode)
    cur = conn.execute(
        "INSERT INTO notices (source_id, fingerprint, title, url, published_date, first_seen, raw_text, "
        "text_hash, notice_type, summary, applies_to_json, fees_json, action_required, extraction_mode, "
        "review_status, issues_json, version, last_changed) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)",
        (source_id, fingerprint, raw.title, raw.url, raw.published, now_iso(), text, sha(text),
         cols["notice_type"], cols["summary"], cols["applies_to_json"], cols["fees_json"],
         cols["action_required"], cols["extraction_mode"], cols["review_status"], cols["issues_json"],
         now_iso()))
    notice_id = cur.lastrowid
    conn.execute("INSERT INTO notice_versions (notice_id, version, text_hash, raw_text, seen_at) VALUES (?,?,?,?,?)",
                 (notice_id, 1, sha(text), text, now_iso()))
    _replace_deadlines(conn, notice_id, result.data["deadlines"])
    _link_related_notice(conn, source_id, notice_id, raw.title, result.data["deadlines"])
    alerts.schedule_for_notice(conn, notice_id)
    alerts.send_notice_alerts(conn, notice_id, "new")
    return notice_id


def _handle_revision(conn, existing, raw: RawNotice, text: str) -> int:
    notice_id = existing["id"]
    old_deadlines = _stored_deadlines(conn, notice_id)
    result, mode = extract_and_validate(raw.title, text, raw.published or existing["published_date"])
    cols = _notice_columns(result, mode)
    version = existing["version"] + 1
    summary = change_detector.describe_change(existing["title"], old_deadlines, result.data["deadlines"],
                                              existing["raw_text"] or "", text)
    conn.execute(
        "UPDATE notices SET raw_text=?, text_hash=?, notice_type=?, summary=?, applies_to_json=?, fees_json=?, "
        "action_required=?, extraction_mode=?, review_status=?, issues_json=?, version=?, last_changed=? "
        "WHERE id=?",
        (text, sha(text), cols["notice_type"], cols["summary"], cols["applies_to_json"], cols["fees_json"],
         cols["action_required"], cols["extraction_mode"], cols["review_status"], cols["issues_json"],
         version, now_iso(), notice_id))
    conn.execute("INSERT INTO notice_versions (notice_id, version, text_hash, raw_text, seen_at) VALUES (?,?,?,?,?)",
                 (notice_id, version, sha(text), text, now_iso()))
    conn.execute("INSERT INTO changes (notice_id, kind, summary, created_at) VALUES (?,?,?,?)",
                 (notice_id, "revised_in_place", summary, now_iso()))
    _replace_deadlines(conn, notice_id, result.data["deadlines"])
    alerts.schedule_for_notice(conn, notice_id)
    alerts.send_notice_alerts(conn, notice_id, "revised", change_summary=summary)
    return notice_id


def _link_related_notice(conn, source_id: int, notice_id: int, title: str, new_deadlines: list[dict]) -> None:
    """If a NEW notice looks like a revision of an older one ("Revised: ..."), record what changed."""
    if not REVISION_WORDS.search(title):
        return
    cleaned = REVISION_WORDS.sub("", title).lower()
    best_id, best_ratio = None, 0.0
    for row in conn.execute("SELECT id, title FROM notices WHERE source_id = ? AND id != ?",
                            (source_id, notice_id)).fetchall():
        ratio = difflib.SequenceMatcher(None, cleaned, REVISION_WORDS.sub("", row["title"]).lower()).ratio()
        if ratio > best_ratio:
            best_id, best_ratio = row["id"], ratio
    if best_id is None or best_ratio < 0.6:
        return
    old_title = conn.execute("SELECT title FROM notices WHERE id = ?", (best_id,)).fetchone()["title"]
    summary = change_detector.describe_change(old_title, _stored_deadlines(conn, best_id), new_deadlines,
                                              report_removed=False)
    conn.execute("INSERT INTO changes (notice_id, related_notice_id, kind, summary, created_at) VALUES (?,?,?,?,?)",
                 (notice_id, best_id, "revision_notice", summary, now_iso()))


# ---------------------------------------------------------------------------
# One notice, one source, all sources
# ---------------------------------------------------------------------------
def _should_recheck(existing, recheck_days: int) -> bool:
    try:
        first_seen = datetime.fromisoformat(existing["first_seen"])
    except ValueError:
        return False
    return datetime.now() - first_seen <= timedelta(days=recheck_days)


def process_raw_notice(conn, source_id: int, source_name: str, raw: RawNotice, recheck_days: int) -> str:
    """Returns 'new', 'revised', 'unchanged' or 'skipped'."""
    fingerprint = sha(f"{source_name}|{raw.url or raw.title}")
    existing = conn.execute("SELECT * FROM notices WHERE fingerprint = ?", (fingerprint,)).fetchone()
    if existing and raw.text is None and not _should_recheck(existing, recheck_days):
        return "unchanged"                                  # old web notice: do not download again

    text = get_notice_text(raw)
    if text is None:
        return "skipped"
    if existing:
        if sha(text) == existing["text_hash"]:
            return "unchanged"
        _handle_revision(conn, existing, raw, text)
        return "revised"
    _handle_new(conn, source_id, fingerprint, raw, text)
    return "new"


def process_source(conn, cfg: dict, recheck_days: int = Config.RECHECK_DAYS) -> Counter:
    stats: Counter = Counter()
    source_id = upsert_source(conn, cfg["name"], cfg["kind"], cfg.get("url") or cfg.get("path"))
    error = None
    try:
        raws = fetcher.fetch_source(cfg)
    except Exception as exc:
        log.error("Source %r failed: %s", cfg["name"], exc)
        stats["errors"] += 1
        conn.execute("INSERT INTO fetch_log (source_id, ran_at, found, new_count, error) VALUES (?,?,0,0,?)",
                     (source_id, now_iso(), str(exc)[:300]))
        return stats

    stats["found"] = len(raws)
    if not raws:
        log.warning("Source %r returned 0 notices. The page layout may have changed - check your selectors.",
                    cfg["name"])
    for raw in raws:
        try:
            outcome = process_raw_notice(conn, source_id, cfg["name"], raw, recheck_days)
            conn.commit()
        except Exception:
            log.exception("Problem processing notice %r", raw.title)
            conn.rollback()
            stats["errors"] += 1
            continue
        stats[outcome] += 1
    conn.execute("INSERT INTO fetch_log (source_id, ran_at, found, new_count, error) VALUES (?,?,?,?,?)",
                 (source_id, now_iso(), stats["found"], stats["new"], error))
    return stats


def run_all(only_source: str | None = None, recheck_days: int = Config.RECHECK_DAYS) -> dict:
    totals: Counter = Counter()
    with connection() as conn:
        for cfg in load_sources():
            if not cfg.get("enabled", True):
                continue
            if only_source and cfg["name"] != only_source:
                continue
            log.info("Checking source: %s", cfg["name"])
            totals.update(process_source(conn, cfg, recheck_days))
    return dict(totals)
