"""Describe what changed when a notice is revised.

Step 1 is plain code: compare the old and new deadline lists. That is exact and cheap.
Step 2 (optional) asks the AI to phrase the change in one friendly sentence.
The AI only rewords facts we already found; it is never the source of the facts.
"""
from __future__ import annotations

import difflib
from datetime import date

from .llm_client import generate_text, llm_enabled


def _pretty(iso: str) -> str:
    try:
        d = date.fromisoformat(iso)
        return f"{d.day} {d.strftime('%b %Y')}"
    except ValueError:
        return iso


def compare_deadlines(old: list[dict], new: list[dict], report_removed: bool = True) -> list[str]:
    """Return plain sentences such as 'Last date moved from 5 Nov 2026 to 12 Nov 2026.'"""
    old_by_label = {d["label"]: d["date"] for d in old}
    new_by_label = {d["label"]: d["date"] for d in new}
    lines: list[str] = []
    for label, new_date in new_by_label.items():
        if label in old_by_label and old_by_label[label] != new_date:
            lines.append(f"{label} moved from {_pretty(old_by_label[label])} to {_pretty(new_date)}.")
        elif label not in old_by_label:
            lines.append(f"New date added: {label} on {_pretty(new_date)}.")
    for label, old_date in old_by_label.items():
        if report_removed and label not in new_by_label:
            lines.append(f"Date removed: {label} ({_pretty(old_date)}).")
    return lines


def text_diff(old_text: str, new_text: str, max_lines: int = 12) -> str:
    diff = difflib.unified_diff(old_text.splitlines(), new_text.splitlines(), lineterm="", n=0)
    changed = [ln for ln in diff if ln.startswith(("+", "-")) and not ln.startswith(("+++", "---"))]
    return "\n".join(changed[:max_lines])


def describe_change(title: str, old_deadlines: list[dict], new_deadlines: list[dict],
                    old_text: str = "", new_text: str = "", report_removed: bool = True) -> str:
    facts = compare_deadlines(old_deadlines, new_deadlines, report_removed)
    if not facts:
        diff = text_diff(old_text, new_text)
        facts = ["The wording of the notice was updated, but no deadline changed."] if diff else \
                ["The notice was updated."]
    plain = " ".join(facts)

    if llm_enabled():
        prompt = (f"Notice title: {title}\nChanges found by code:\n- " + "\n- ".join(facts) +
                  "\n\nWrite ONE short, friendly sentence for students describing these changes. "
                  "Use only the facts above. Do not add any new dates or numbers.")
        answer = generate_text("You write short, accurate notices for university students.", prompt)
        if answer and len(answer) < 400:
            return answer.strip()
    return plain
