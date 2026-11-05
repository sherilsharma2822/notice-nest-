"""Pretend the university edited a notice, so you can watch NoticeNest spot the change.

    python tools/simulate_revision.py          # moves a deadline in a demo notice
    python -m app.jobs.run_once                # NoticeNest sees the edit and alerts students
    python tools/simulate_revision.py --undo   # put the demo notice back
"""
from __future__ import annotations

import sys
from pathlib import Path

FILE = Path(__file__).resolve().parent.parent / "data" / "samples" / "01_exam_form_bca.txt"
BEFORE = "without late fee is {{+10}}"
AFTER = "without late fee is {{+15}}"


def main() -> None:
    undo = "--undo" in sys.argv
    text = FILE.read_text(encoding="utf-8")
    old, new = (AFTER, BEFORE) if undo else (BEFORE, AFTER)
    if old not in text:
        print("Nothing to change (already in that state).")
        return
    FILE.write_text(text.replace(old, new), encoding="utf-8")
    print("Demo notice restored." if undo else "Demo notice edited. Now run: python -m app.jobs.run_once")


if __name__ == "__main__":
    main()
