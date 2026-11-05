"""Ask the AI to turn notice text into structured data (JSON).

Important: the AI's answer is NEVER trusted directly. It always goes through
validator.py, which checks every date and fee against the real notice text.
"""
from __future__ import annotations

from ..config import Config
from .llm_client import generate_json
from .regex_extractor import NOTICE_TYPES

SYSTEM_PROMPT = """You read official university notices from India and return structured data as JSON.

Rules:
- Use ONLY information written in the notice. Never guess or invent anything.
- Dates must be written as YYYY-MM-DD. Indian notices write dates day-month-year (05/11/2026 means 5 November 2026).
- If a date has no year, use the year of the notice date given to you. If that is unknown, set the date to null.
- For every deadline, copy the exact words from the notice that contain the date into "snippet".
- notice_type must be exactly one of: exam_form, fee, result, scholarship, timetable, admission, holiday, other.
- applies_to.courses: short uppercase codes without dots (BCA, MCA, BTECH, MBA, BSC ...).
- applies_to.semesters: a list of integers. If the notice is for every student set applies_to.all to true.
- If the notice does not say who it is for, leave the lists empty and set all to false.
- fees: amounts in rupees as plain numbers.
- summary: at most two short sentences in simple English.
- action_required: what a student must do, in one short sentence (or an empty string).

Return ONLY one JSON object with exactly these keys:
{"notice_type": "", "summary": "", "applies_to": {"all": false, "courses": [], "semesters": [], "batches": []},
 "deadlines": [{"label": "", "date": "YYYY-MM-DD", "snippet": ""}],
 "fees": [{"label": "", "amount": 0}], "action_required": ""}"""


def _as_list(value) -> list:
    return value if isinstance(value, list) else []


def normalize_output(obj: dict) -> dict:
    """Make sure the AI's answer has every key, with the right basic types."""
    applies = obj.get("applies_to") if isinstance(obj.get("applies_to"), dict) else {}
    ntype = obj.get("notice_type")
    return {
        "notice_type": ntype if ntype in NOTICE_TYPES else "other",
        "summary": str(obj.get("summary") or ""),
        "applies_to": {
            "all": bool(applies.get("all")),
            "courses": [str(c) for c in _as_list(applies.get("courses"))],
            "semesters": [s for s in _as_list(applies.get("semesters")) if str(s).isdigit()],
            "batches": [str(b) for b in _as_list(applies.get("batches"))],
        },
        "deadlines": [d for d in _as_list(obj.get("deadlines")) if isinstance(d, dict)],
        "fees": [f for f in _as_list(obj.get("fees")) if isinstance(f, dict)],
        "action_required": str(obj.get("action_required") or ""),
    }


def extract_with_llm(title: str, text: str, published: str | None) -> dict | None:
    """Returns structured data, or None if the AI is off or failed (caller then uses regex)."""
    user_prompt = (f"Notice title: {title}\nNotice date: {published or 'unknown'}\n\n"
                   f"Notice text:\n{text[:Config.MAX_TEXT_CHARS_FOR_LLM]}")
    obj = generate_json(SYSTEM_PROMPT, user_prompt)
    if obj is None:
        return None
    return normalize_output(obj)
