"""Tests the AI path WITHOUT using the internet: the AI's answer is faked."""
import json

from app.config import Config
from app.services import ai_extractor, llm_client
from app.services.validator import validate

TEXT = "Last date for the examination form is 05.11.2026. For BCA III Semester."


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code, self._payload, self.text = status_code, payload or {}, "fake"

    def json(self):
        return self._payload


def _gemini_reply(obj):
    return FakeResponse(200, {"candidates": [{"content": {"parts": [{"text": json.dumps(obj)}]}}]})


def _turn_on_fake_gemini(monkeypatch, replies):
    monkeypatch.setattr(Config, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(Config, "GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr(Config, "LLM_MAX_RETRIES", 2)
    monkeypatch.setattr(llm_client.time, "sleep", lambda _s: None)       # do not really wait
    calls = []

    def fake_call(system, user, want_json):
        calls.append(1)
        return replies[min(len(calls) - 1, len(replies) - 1)]

    monkeypatch.setattr(llm_client, "_call_gemini", fake_call)
    return calls


def test_ai_answer_is_parsed_and_invented_date_is_caught(temp_db, monkeypatch):
    answer = {"notice_type": "exam_form", "summary": "Fill the form.",
              "applies_to": {"all": False, "courses": ["BCA"], "semesters": [3], "batches": []},
              "deadlines": [{"label": "Last date", "date": "2026-11-05", "snippet": "Last date for the examination form is 05.11.2026"},
                            {"label": "Exams start", "date": "2026-12-01", "snippet": "invented"}],
              "fees": [], "action_required": "Fill the form."}
    _turn_on_fake_gemini(monkeypatch, [_gemini_reply(answer)])
    data = ai_extractor.extract_with_llm("Exam form", TEXT, "2026-10-20")
    result = validate(data, TEXT, "2026-10-20")
    verified = {d["date"]: d["verified"] for d in result.data["deadlines"]}
    assert verified == {"2026-11-05": True, "2026-12-01": False}
    assert result.status == "needs_review"


def test_answer_is_cached_so_the_second_call_is_free(temp_db, monkeypatch):
    calls = _turn_on_fake_gemini(monkeypatch, [_gemini_reply({"notice_type": "other"})])
    ai_extractor.extract_with_llm("t", TEXT, None)
    ai_extractor.extract_with_llm("t", TEXT, None)
    assert len(calls) == 1


def test_busy_server_is_retried_then_succeeds(temp_db, monkeypatch):
    calls = _turn_on_fake_gemini(monkeypatch, [FakeResponse(429), _gemini_reply({"notice_type": "fee"})])
    assert ai_extractor.extract_with_llm("t", TEXT, None)["notice_type"] == "fee"
    assert len(calls) == 2


def test_bad_key_gives_none_so_the_app_falls_back_to_regex(temp_db, monkeypatch):
    calls = _turn_on_fake_gemini(monkeypatch, [FakeResponse(401)])
    assert ai_extractor.extract_with_llm("t", TEXT, None) is None
    assert len(calls) == 1                      # no pointless retries on a wrong key


def test_json_inside_code_fences_is_understood():
    assert llm_client.parse_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    assert llm_client.parse_json_object("sorry, no") is None
