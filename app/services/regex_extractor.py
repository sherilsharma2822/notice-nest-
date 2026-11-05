"""Basic mode: find dates, fees, notice type and eligibility using patterns only (no AI).

This is also the BASELINE we compare the AI against in eval/run_eval.py, and the
safety net used when the AI is switched off or its free quota runs out.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

NOTICE_TYPES = ["exam_form", "fee", "result", "scholarship", "timetable", "admission", "holiday", "other"]

MONTH_NUM = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}

# Month names. The trailing \b stops "Marks 12 2026" from being read as "Mar 12 2026".
_MONTHS = (r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|"
           r"Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\b")

# 05.11.2026 / 5/11/26 / 05-11-2026  (Indian notices write day first)
_NUMERIC_DATE = re.compile(r"\b(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{4}|\d{2})\b")
# 5th November 2026 / 05 Nov, 2026
_DAY_MONTH_YEAR = re.compile(
    rf"\b(\d{{1,2}})(?:st|nd|rd|th)?[\s,.\-]*({_MONTHS})\.?[\s,.\-]*(\d{{4}})\b", re.I)
# November 5, 2026 / Nov 5th 2026
_MONTH_DAY_YEAR = re.compile(
    rf"\b({_MONTHS})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b", re.I)


@dataclass
class DateHit:
    value: date
    start: int
    end: int
    snippet: str


def _make_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def _year(text: str) -> int:
    y = int(text)
    return 2000 + y if y < 100 else y


def _snippet(text: str, start: int, end: int) -> str:
    """The line of text around a match (shortened if very long)."""
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end == -1:
        line_end = len(text)
    if line_end - line_start > 220:
        line_start, line_end = max(line_start, start - 90), min(line_end, end + 90)
    return re.sub(r"\s+", " ", text[line_start:line_end]).strip()


def find_dates(text: str) -> list[DateHit]:
    """Return every calendar date written in the text, in reading order."""
    found: list[tuple[int, int, date]] = []
    for m in _NUMERIC_DATE.finditer(text):
        d, mo, y = m.groups()
        v = _make_date(_year(y), int(mo), int(d))
        if v:
            found.append((m.start(), m.end(), v))
    for m in _DAY_MONTH_YEAR.finditer(text):
        d, mon, y = m.groups()
        v = _make_date(int(y), MONTH_NUM[mon[:3].lower()], int(d))
        if v:
            found.append((m.start(), m.end(), v))
    for m in _MONTH_DAY_YEAR.finditer(text):
        mon, d, y = m.groups()
        v = _make_date(int(y), MONTH_NUM[mon[:3].lower()], int(d))
        if v:
            found.append((m.start(), m.end(), v))

    found.sort()
    hits: list[DateHit] = []
    last_end = -1
    for start, end, v in found:
        if start < last_end:          # overlaps a date we already took
            continue
        hits.append(DateHit(v, start, end, _snippet(text, start, end)))
        last_end = end
    return hits


# ---------------------------------------------------------------------------
# Notice type
# ---------------------------------------------------------------------------
_TYPE_KEYWORDS: dict[str, list[tuple[str, int]]] = {
    "exam_form": [("examination form", 4), ("exam form", 4), ("examination application", 4),
                  ("form fill", 3), ("filling of examination", 4), ("fill up", 2)],
    "timetable": [("time table", 4), ("timetable", 4), ("date sheet", 4), ("datesheet", 4),
                  ("schedule of examination", 4), ("examination schedule", 3)],
    "result": [("result", 3), ("declared", 2), ("revaluation", 4), ("re-evaluation", 4),
               ("re-totaling", 4), ("retotaling", 4), ("scrutiny", 2)],
    "fee": [("fee", 2), ("fees", 2), ("payment", 2), ("challan", 3), ("dues", 2)],
    "scholarship": [("scholarship", 5), ("stipend", 3), ("fellowship", 3)],
    "admission": [("admission", 4), ("counselling", 4), ("counseling", 4), ("merit list", 4),
                  ("seat allotment", 4)],
    "holiday": [("holiday", 5), ("will remain closed", 5), ("vacation", 3)],
}


def classify_type(title: str, text: str) -> str:
    title_l, text_l = title.lower(), text.lower()
    best_type, best_score = "other", 0
    for ntype, words in _TYPE_KEYWORDS.items():
        score = 0
        for word, weight in words:
            score += weight * 3 * (1 if word in title_l else 0)
            score += weight * min(text_l.count(word), 2)
        if score > best_score:
            best_type, best_score = ntype, score
    return best_type if best_score >= 3 else "other"


# ---------------------------------------------------------------------------
# Deadlines
# ---------------------------------------------------------------------------
def label_for_context(context: str) -> str:
    s = context.lower()
    if "without late fee" in s or "without fine" in s or "without late fine" in s:
        return "Last date without late fee"
    if "late fee" in s or "late fine" in s or "with fine" in s:
        return "Last date with late fee"
    if any(k in s for k in ("last date", "last day", "deadline", "on or before", "not later than",
                            "till ", "upto", "up to", "before ")):
        return "Last date"
    if "exam" in s and any(k in s for k in ("commence", "start", "begin", "from")):
        return "Exams start"
    if "result" in s:
        return "Result date"
    if "resume" in s:
        return "Classes resume"
    if "admit card" in s:
        return "Admit cards"
    if "counsel" in s:
        return "Counselling"
    if "verification" in s:
        return "Verification"
    if "end on" in s or "ends on" in s:
        return "Ends"
    if "holiday" in s or "closed" in s:
        return "Holiday"
    return "Date mentioned"


def _is_issue_date(text: str, hit: DateHit) -> bool:
    """True for the date a notice was written ("Date: 12.10.2026"), which is not a deadline."""
    if hit.start > 400:
        return False
    before = text[max(0, hit.start - 14):hit.start].lower()
    return bool(re.search(r"\bdate[d]?\b[\s:.\-]*$|\bdt\.?[\s:.\-]*$", before))


def extract_deadlines(text: str) -> list[dict]:
    deadlines: list[dict] = []
    seen: set[tuple[str, date]] = set()
    hits = find_dates(text)
    for i, hit in enumerate(hits):
        if _is_issue_date(text, hit):
            continue
        line_start = text.rfind("\n", 0, hit.start) + 1
        line_end = text.find("\n", hit.end)
        line_end = len(text) if line_end == -1 else line_end
        prev_end = hits[i - 1].end if i > 0 else 0
        next_start = hits[i + 1].start if i + 1 < len(hits) else len(text)

        # Label from the words just BEFORE the date (back to the previous date or line start).
        label = label_for_context(text[max(line_start, prev_end, hit.start - 70):hit.start])
        if label == "Date mentioned":
            # e.g. "05.11.2026 is the last date": look at the few words AFTER the date.
            label = label_for_context(text[hit.end:min(line_end, next_start, hit.end + 40)])
        key = (label, hit.value)
        if key in seen:
            continue
        seen.add(key)
        deadlines.append({"label": label, "date": hit.value.isoformat(), "snippet": hit.snippet[:300]})
    return deadlines


# ---------------------------------------------------------------------------
# Fees
# ---------------------------------------------------------------------------
_FILLER_WORDS = {"is", "and", "of", "the", "a", "an", "to", "be", "at", "for", "rs", "inr", "per", "will", "shall", "are", "pay"}
_AMOUNT = re.compile(r"(?:Rs\.?|INR|\u20b9)\s*([0-9][0-9,]*(?:\.\d{1,2})?)", re.I)


def extract_amounts(text: str) -> list[dict]:
    fees: list[dict] = []
    for m in _AMOUNT.finditer(text):
        try:
            value = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        line_start = text.rfind("\n", 0, m.start()) + 1
        window = text[max(line_start, m.start() - 60):m.start()]
        before = re.sub(r"[^A-Za-z ]", " ", re.split(r"\d", window)[-1])   # words after the last number
        words = before.split()[-5:]
        while words and words[0].lower() in _FILLER_WORDS | {"date"}:
            words.pop(0)
        while words and words[-1].lower() in _FILLER_WORDS:
            words.pop()
        label = " ".join(words).strip().capitalize() or "Amount"
        fees.append({"label": label[:60], "amount": int(value) if value.is_integer() else value})
    return fees


# ---------------------------------------------------------------------------
# Who the notice is for
# ---------------------------------------------------------------------------
_COURSES: list[tuple[str, re.Pattern]] = [
    ("BCA", re.compile(r"\bB\.?\s?C\.?\s?A\b", re.I)),
    ("MCA", re.compile(r"\bM\.?\s?C\.?\s?A\b", re.I)),
    ("BTECH", re.compile(r"\bB\.?\s?Tech\b", re.I)),
    ("MTECH", re.compile(r"\bM\.?\s?Tech\b", re.I)),
    ("BBA", re.compile(r"\bB\.?\s?B\.?\s?A\b", re.I)),
    ("MBA", re.compile(r"\bM\.?\s?B\.?\s?A\b", re.I)),
    ("BSC", re.compile(r"\bB\.?\s?Sc\b", re.I)),
    ("MSC", re.compile(r"\bM\.?\s?Sc\b", re.I)),
    ("BCOM", re.compile(r"\bB\.?\s?Com\b", re.I)),
    ("MCOM", re.compile(r"\bM\.?\s?Com\b", re.I)),
    ("BED", re.compile(r"\bB\.?\s?Ed\b", re.I)),
    ("LLB", re.compile(r"\bLL\.?\s?B\b", re.I)),
    ("PHD", re.compile(r"\bPh\.?\s?D\b", re.I)),
    # BA and MA are case-sensitive on purpose, so ordinary words are not mistaken for courses.
    ("BA", re.compile(r"\bB\.A\.?(?!\w)|\bBA\b(?!['\u2019])")),
    ("MA", re.compile(r"\bM\.A\.?(?!\w)|\bMA\b(?!['\u2019])")),
]

_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10}
_SEM_WORD = r"(?:[Ss]emesters?|SEMESTERS?|[Ss]ems?\b|SEMS?\b)"
_TOKEN = r"(?:\d{1,2}(?:st|nd|rd|th)?|[IVX]{1,4})"
_SEM_BEFORE = re.compile(rf"((?:{_TOKEN}\b\s*(?:,|&|and|/)?\s*){{1,6}}){_SEM_WORD}")
_SEM_AFTER = re.compile(rf"{_SEM_WORD}\s*[-:.]?\s*((?:(?:\d{{1,2}}|[IVX]{{1,4}})\b\s*(?:,|&|and|/)?\s*){{1,6}})")
_SEM_TOKEN = re.compile(r"\d{1,2}|[IVX]{1,4}")
_BATCH = re.compile(r"\bbatch(?:es)?\s*(?:of\s*)?(20\d{2})|\b(20\d{2})(?:\s*[-/]\s*(?:20)?\d{2})?\s*batch", re.I)
_ALL_STUDENTS = re.compile(r"\ball\s+(?:the\s+)?(?:students|candidates|scholars|learners)\b", re.I)


def find_courses(text: str) -> list[str]:
    return [code for code, pattern in _COURSES if pattern.search(text)]


def _semester_numbers(chunk: str) -> list[int]:
    numbers = []
    for token in _SEM_TOKEN.findall(chunk):
        n = _ROMAN.get(token) if token.isalpha() else int(token)
        if n and 1 <= n <= 10:
            numbers.append(n)
    return numbers


def find_semesters(text: str) -> list[int]:
    found: set[int] = set()
    for m in _SEM_BEFORE.finditer(text):
        found.update(_semester_numbers(m.group(1)))
    for m in _SEM_AFTER.finditer(text):
        found.update(_semester_numbers(m.group(1)))
    if not found:
        if re.search(r"\bodd\s+sem", text, re.I):
            found.update([1, 3, 5, 7, 9])
        elif re.search(r"\beven\s+sem", text, re.I):
            found.update([2, 4, 6, 8, 10])
    return sorted(found)


def extract_applies_to(text: str, notice_type: str = "other") -> dict:
    courses = find_courses(text)
    semesters = find_semesters(text)
    batches = sorted({g for m in _BATCH.finditer(text) for g in m.groups() if g})
    everyone = False
    if not courses and not semesters:
        everyone = bool(_ALL_STUDENTS.search(text)) or notice_type == "holiday"
    return {"all": everyone, "courses": courses, "semesters": semesters, "batches": batches}


# ---------------------------------------------------------------------------
# Put it all together
# ---------------------------------------------------------------------------
def _short_summary(text: str) -> str:
    """First real sentences of the notice, skipping letterhead lines such as 'EXAMINATION BRANCH'."""
    lines = []
    for ln in text.splitlines():
        ln = ln.strip()
        if len(ln) < 30 or ln.isupper() or re.match(r"(notice|no\.|ref|memo|circular no)\b", ln, re.I):
            continue
        lines.append(ln)
    return " ".join(lines[:2])[:240]


def extract_all(title: str, text: str) -> dict:
    """Same output shape as the AI extractor, so the rest of the app treats both alike."""
    ntype = classify_type(title, text)
    return {
        "notice_type": ntype,
        "summary": _short_summary(text),
        "applies_to": extract_applies_to(f"{title}\n{text}", ntype),
        "deadlines": extract_deadlines(text),
        "fees": extract_amounts(text),
        "action_required": "",
    }
