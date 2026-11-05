"""The ONLY file that talks to an AI service.

Why one file? Free AI tiers change their limits and model names often. If everything
goes through here, switching provider or fixing an error means editing one place.

Features: timeout, retry with waiting, answer cache (same text = no second API call),
and it never crashes the app: on any problem it returns None and the caller falls back
to basic (regex) mode.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time

import requests

from ..config import Config
from ..db import connection, now_iso

log = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def llm_enabled() -> bool:
    if Config.LLM_PROVIDER == "gemini":
        return bool(Config.GEMINI_API_KEY)
    if Config.LLM_PROVIDER == "groq":
        return bool(Config.GROQ_API_KEY)
    return False


def _model_name() -> str:
    return Config.GEMINI_MODEL if Config.LLM_PROVIDER == "gemini" else Config.GROQ_MODEL


def _cache_key(system: str, user: str) -> str:
    raw = f"{Config.LLM_PROVIDER}|{_model_name()}|{system}|{user}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cache_get(key: str) -> str | None:
    try:
        with connection() as conn:
            row = conn.execute("SELECT response FROM llm_cache WHERE cache_key = ?", (key,)).fetchone()
            return row["response"] if row else None
    except Exception:
        return None


def _cache_put(key: str, response: str) -> None:
    try:
        with connection() as conn:
            conn.execute("INSERT OR REPLACE INTO llm_cache (cache_key, response, created_at) VALUES (?, ?, ?)",
                         (key, response, now_iso()))
    except Exception:
        log.warning("Could not write to the LLM cache.")


def _call_gemini(system: str, user: str, want_json: bool) -> requests.Response:
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {"temperature": 0},
    }
    if want_json:
        payload["generationConfig"]["responseMimeType"] = "application/json"
    return requests.post(
        GEMINI_URL.format(model=Config.GEMINI_MODEL),
        headers={"x-goog-api-key": Config.GEMINI_API_KEY, "Content-Type": "application/json"},
        json=payload, timeout=Config.LLM_TIMEOUT_SECONDS)


def _call_groq(system: str, user: str, want_json: bool) -> requests.Response:
    payload = {
        "model": Config.GROQ_MODEL,
        "temperature": 0,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    return requests.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {Config.GROQ_API_KEY}", "Content-Type": "application/json"},
        json=payload, timeout=Config.LLM_TIMEOUT_SECONDS)


def _extract_text(provider: str, data: dict) -> str | None:
    try:
        if provider == "gemini":
            return data["candidates"][0]["content"]["parts"][0]["text"]
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None


def generate_text(system: str, user: str, want_json: bool = False) -> str | None:
    """Ask the AI a question. Returns the answer text, or None if anything goes wrong."""
    if not llm_enabled():
        return None

    key = _cache_key(system, user)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    provider = Config.LLM_PROVIDER
    caller = _call_gemini if provider == "gemini" else _call_groq
    for attempt in range(Config.LLM_MAX_RETRIES + 1):
        try:
            resp = caller(system, user, want_json)
        except requests.RequestException as exc:
            log.warning("LLM request failed (%s). Attempt %d.", exc.__class__.__name__, attempt + 1)
            resp = None
        if resp is not None:
            if resp.status_code == 200:
                answer = _extract_text(provider, resp.json())
                if answer:
                    _cache_put(key, answer)
                    return answer
                log.warning("LLM answered 200 but the reply had no text.")
                return None
            if resp.status_code in (429, 500, 502, 503, 504):
                log.warning("LLM busy or rate limited (HTTP %d). Attempt %d.", resp.status_code, attempt + 1)
            else:
                # 400/401/403/404: wrong key, wrong model name, bad request. Retrying will not help.
                log.error("LLM error HTTP %d: %s. Check the key and model name in .env.",
                          resp.status_code, resp.text[:200].replace("\n", " "))
                return None
        time.sleep(2 ** attempt * 2)
    return None


def parse_json_object(answer: str | None) -> dict | None:
    """Pull a JSON object out of an AI answer, even if it is wrapped in ```json fences."""
    if not answer:
        return None
    cleaned = re.sub(r"^```(?:json)?|```$", "", answer.strip(), flags=re.M).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        obj = json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def generate_json(system: str, user: str) -> dict | None:
    return parse_json_object(generate_text(system, user, want_json=True))
