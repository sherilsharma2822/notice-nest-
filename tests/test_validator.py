from app.services.validator import validate

TEXT = "Last date for the form is 05.11.2026. Fee is Rs. 500. For BCA III Semester."


def _data(**changes):
    base = {"notice_type": "exam_form", "summary": "s", "applies_to": {"all": False, "courses": ["BCA"],
            "semesters": [3], "batches": []},
            "deadlines": [{"label": "Last date", "date": "2026-11-05", "snippet": "Last date for the form is 05.11.2026"}],
            "fees": [{"label": "Fee", "amount": 500}], "action_required": ""}
    base.update(changes)
    return base


def test_good_data_is_verified():
    result = validate(_data(), TEXT, "2026-10-20")
    assert result.status == "verified"
    assert result.data["deadlines"][0]["verified"] is True


def test_invented_date_is_kept_but_flagged():
    bad = _data(deadlines=[{"label": "Last date", "date": "2026-11-09", "snippet": ""}])
    result = validate(bad, TEXT, "2026-10-20")
    assert result.status == "needs_review"
    assert result.data["deadlines"][0]["verified"] is False       # shown with a warning, not hidden


def test_invented_fee_is_dropped():
    bad = _data(fees=[{"label": "Fee", "amount": 9999}])
    result = validate(bad, TEXT, "2026-10-20")
    assert result.data["fees"] == []
    assert result.status == "needs_review"


def test_fake_snippet_is_replaced_with_real_text():
    bad = _data(deadlines=[{"label": "Last date", "date": "2026-11-05", "snippet": "made up words"}])
    result = validate(bad, TEXT, "2026-10-20")
    assert "05.11.2026" in result.data["deadlines"][0]["snippet"]


def test_unknown_type_becomes_other():
    assert validate(_data(notice_type="banana"), TEXT).data["notice_type"] == "other"


def test_empty_text_needs_review():
    assert validate(_data(), "").status == "needs_review"


def test_deadline_word_without_a_complete_date_needs_review():
    result = validate({"notice_type": "other", "deadlines": [], "fees": [], "applies_to": {}},
                      "The last date is 8 November.", "2026-10-20")
    assert result.status == "needs_review"
