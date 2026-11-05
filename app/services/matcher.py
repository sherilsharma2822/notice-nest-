"""Decide whether a notice applies to a student: "yes", "maybe" or "no".

Design rule: a missed deadline is worse than an extra alert.
So when the notice does not say who it is for, the answer is "maybe", never "no".
"""
from __future__ import annotations

import re

COURSE_CHOICES = ["BCA", "MCA", "BTECH", "MTECH", "BBA", "MBA", "BSC", "MSC",
                  "BCOM", "MCOM", "BA", "MA", "BED", "LLB", "PHD"]


def normalize_course(value: str) -> str:
    """"B. Tech." -> "BTECH",  "b.c.a" -> "BCA"."""
    return re.sub(r"[^A-Za-z]", "", value or "").upper()


def match_user(applies_to: dict, course: str, semester: int, batch: str | None = None) -> str:
    applies_to = applies_to or {}
    if applies_to.get("all"):
        return "yes"

    courses = [normalize_course(c) for c in applies_to.get("courses", [])]
    semesters = [int(s) for s in applies_to.get("semesters", [])]
    batches = [str(b) for b in applies_to.get("batches", [])]

    if not courses and not semesters:
        return "maybe"      # the notice does not say who it is for

    course_ok = not courses or normalize_course(course) in courses
    semester_ok = not semesters or int(semester) in semesters
    if not (course_ok and semester_ok):
        return "no"
    if batches and batch and not any(str(batch).startswith(b) for b in batches):
        return "maybe"
    return "yes"
