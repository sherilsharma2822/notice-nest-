from app.services.change_detector import compare_deadlines


def test_moved_added_removed():
    old = [{"label": "Last date", "date": "2026-11-05"}, {"label": "Exams start", "date": "2026-12-01"}]
    new = [{"label": "Last date", "date": "2026-11-12"}, {"label": "Late fee date", "date": "2026-11-20"}]
    lines = compare_deadlines(old, new)
    assert any("moved from 5 Nov 2026 to 12 Nov 2026" in line for line in lines)
    assert any("New date added" in line for line in lines)
    assert any("Date removed" in line for line in lines)


def test_correction_notice_does_not_report_removed():
    old = [{"label": "Exams start", "date": "2026-12-01"}]
    assert compare_deadlines(old, [], report_removed=False) == []
