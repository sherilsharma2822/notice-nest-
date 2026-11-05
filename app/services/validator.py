"""Check what the extractor found against the real notice text.

This is the safety layer. An AI can invent a date; this module notices.
- A date is "verified" only if that exact calendar date is written in the notice.
- A fee is kept only if the number appears in the notice.
- Anything doubtful is flagged "needs_review" and shown to students with a warning.
Nothing doubtful is silently hidden.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from .matcher import normalize_course
from .regex_extractor import NOTICE_TYPES, find_courses, find_dates


@dataclass
class ValidationResult:
    data: dict
    issues: list[str] = field(default_factory=list)
    status: str = "verified"       # "verified" or "needs_review"


def parse_iso(value) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _squash(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


def validate(data: dict, text: str, published: str | None = None) -> ValidationResult:
    issues: list[str] = []
    serious = False
    text = text or ""

    if not text.strip():
        issues.append("No readable text (the notice may be a scan). Open the original notice.")
        serious = True

    # --- type ---
    ntype = data.get("notice_type")
    if ntype not in NOTICE_TYPES:
        issues.append(f"Unknown notice type {ntype!r}; using 'other'.")
        ntype = "other"

    # --- deadlines ---
    text_dates = {hit.value: hit for hit in find_dates(text)}
    reference = parse_iso(published) or date.today()
    earliest, latest = reference - timedelta(days=45), reference + timedelta(days=400)
    squashed_text = _squash(text)

    deadlines, seen = [], set()
    for item in data.get("deadlines", []) or []:
        due = parse_iso(item.get("date"))
        if due is None:
            issues.append(f"Dropped a deadline with an unreadable date: {item.get('date')!r}.")
            serious = True
            continue
        verified = due in text_dates
        if not verified:
            issues.append(f"The date {due.isoformat()} is not written in the notice text.")
            serious = True
        if not (earliest <= due <= latest):
            issues.append(f"The date {due.isoformat()} is far from the notice date; please check it.")
            serious = True
            verified = False

        snippet = re.sub(r"\s+", " ", str(item.get("snippet") or "")).strip()
        if snippet and _squash(snippet) not in squashed_text:
            issues.append("A quoted snippet was not found word-for-word in the notice.")
            snippet = text_dates[due].snippet if due in text_dates else ""
        if not snippet and due in text_dates:
            snippet = text_dates[due].snippet

        label = str(item.get("label") or "Deadline").strip()[:80] or "Deadline"
        key = (label, due)
        if key in seen:
            continue
        seen.add(key)
        deadlines.append({"label": label, "date": due.isoformat(),
                          "snippet": snippet[:300], "verified": verified})

    # A notice that talks about a deadline but gave us no readable date must not look "fine".
    if not deadlines and re.search(r"last date|last day|deadline|on or before|not later than", text, re.I):
        issues.append("The notice mentions a deadline, but no complete date (with year) could be read.")
        serious = True

    # --- fees ---
    numbers_in_text = set()
    for raw in re.findall(r"\d[\d,]*(?:\.\d+)?", text):
        try:
            numbers_in_text.add(float(raw.replace(",", "").rstrip(".")))
        except ValueError:
            pass
    fees = []
    for item in data.get("fees", []) or []:
        try:
            amount = float(item.get("amount"))
        except (TypeError, ValueError):
            issues.append("Dropped a fee with an unreadable amount.")
            serious = True
            continue
        if amount in numbers_in_text:
            fees.append({"label": str(item.get("label") or "Amount")[:60],
                         "amount": int(amount) if amount.is_integer() else amount})
        else:
            issues.append(f"Dropped a fee of {amount:g} because that number is not in the notice.")
            serious = True

    # --- who it applies to ---
    raw_applies = data.get("applies_to") or {}
    courses = sorted({normalize_course(c) for c in raw_applies.get("courses", []) if normalize_course(c)})
    semesters = sorted({int(s) for s in raw_applies.get("semesters", [])
                        if str(s).isdigit() and 1 <= int(s) <= 12})
    batches = sorted({str(b) for b in raw_applies.get("batches", []) if str(b).strip()})
    in_text = set(find_courses(text))
    for course in courses:
        if course not in in_text:
            issues.append(f"Course {course} is not written in the notice (inferred).")
    applies_to = {"all": bool(raw_applies.get("all")), "courses": courses,
                  "semesters": semesters, "batches": batches}

    cleaned = {
        "notice_type": ntype,
        "summary": re.sub(r"\s+", " ", str(data.get("summary") or "")).strip()[:300],
        "applies_to": applies_to,
        "deadlines": deadlines,
        "fees": fees,
        "action_required": re.sub(r"\s+", " ", str(data.get("action_required") or "")).strip()[:300],
    }
    return ValidationResult(cleaned, issues, "needs_review" if serious else "verified")
