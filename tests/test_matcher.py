from app.services.matcher import match_user, normalize_course


def test_normalize_course():
    assert normalize_course("B. Tech.") == "BTECH"
    assert normalize_course("b.c.a") == "BCA"


def test_everyone():
    assert match_user({"all": True}, "BCA", 3) == "yes"


def test_exact_match_and_mismatch():
    notice = {"courses": ["BCA"], "semesters": [3, 5]}
    assert match_user(notice, "BCA", 3) == "yes"
    assert match_user(notice, "BCA", 4) == "no"
    assert match_user(notice, "MCA", 3) == "no"


def test_unknown_audience_is_maybe_not_no():
    assert match_user({}, "BCA", 3) == "maybe"
    assert match_user({"courses": [], "semesters": []}, "BCA", 3) == "maybe"


def test_semester_only_notice_applies_to_all_courses():
    assert match_user({"semesters": [1]}, "MBA", 1) == "yes"
