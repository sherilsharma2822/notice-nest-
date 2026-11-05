from datetime import date

from app.services import regex_extractor as rx


def test_finds_dates_in_common_indian_formats():
    text = "Submit by 05.11.2026. Late fee till 12 November 2026 and 3/12/26. Also Nov 20, 2026."
    found = [hit.value for hit in rx.find_dates(text)]
    assert date(2026, 11, 5) in found
    assert date(2026, 11, 12) in found
    assert date(2026, 12, 3) in found           # day first: 3 December
    assert date(2026, 11, 20) in found


def test_ignores_impossible_dates_and_words_that_look_like_months():
    assert rx.find_dates("Marks 12 2026 and 31.02.2026") == []


def test_issue_date_is_not_a_deadline():
    text = "Date: 12.10.2026\nLast date for the form is 05.11.2026."
    dates = [d["date"] for d in rx.extract_deadlines(text)]
    assert dates == ["2026-11-05"]


def test_labels_follow_the_words_before_each_date():
    text = "Fee without late fee is 05.11.2026 and with late fee Rs. 500 is 12.11.2026."
    labels = {d["date"]: d["label"] for d in rx.extract_deadlines(text)}
    assert labels["2026-11-05"] == "Last date without late fee"
    assert labels["2026-11-12"] == "Last date with late fee"


def test_classifies_notice_types():
    assert rx.classify_type("Examination Form for BCA", "") == "exam_form"
    assert rx.classify_type("Time Table for MCA", "") == "timetable"
    assert rx.classify_type("Holiday on Diwali", "") == "holiday"
    assert rx.classify_type("Hostel circular", "Contact the warden.") == "other"


def test_semesters_roman_ordinal_and_odd_even():
    assert rx.find_semesters("BCA III Semester and V Semester") == [3, 5]
    assert rx.find_semesters("B.Tech 2nd, 4th and 6th semester") == [2, 4, 6]
    assert rx.find_semesters("for the odd semester examinations") == [1, 3, 5, 7, 9]
    assert rx.find_semesters("Semester examinations 2026") == []     # a year is not a semester


def test_courses():
    assert rx.find_courses("Students of B.Tech and MCA") == ["MCA", "BTECH"]
    assert rx.find_courses("Dr. Sharma and MA'AM") == []


def test_amounts_with_indian_commas():
    fees = rx.extract_amounts("Pay Rs. 1,250/- and INR 42,500.50 online.")
    assert [f["amount"] for f in fees] == [1250, 42500.5]
