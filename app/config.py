"""All settings in one place. Values come from the .env file (see .env.example)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


class Config:
    # --- Flask ---
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")

    # --- Paths ---
    BASE_DIR = BASE_DIR
    DATA_DIR = BASE_DIR / "data"
    DB_PATH = Path(os.getenv("DB_PATH", DATA_DIR / "noticenest.db"))
    SOURCES_FILE = BASE_DIR / "config" / "sources.yaml"
    DOWNLOAD_DIR = DATA_DIR / "downloads"
    EVAL_RESULTS_FILE = BASE_DIR / "eval" / "results" / "latest.json"

    # --- AI extraction ("none", "gemini" or "groq") ---
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "none").strip().lower()
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    LLM_TIMEOUT_SECONDS = _int("LLM_TIMEOUT_SECONDS", 40)
    LLM_MAX_RETRIES = _int("LLM_MAX_RETRIES", 2)
    MAX_TEXT_CHARS_FOR_LLM = _int("MAX_TEXT_CHARS_FOR_LLM", 12000)

    # --- Reminders ---
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = _int("SMTP_PORT", 587)
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM = os.getenv("SMTP_FROM", "") or os.getenv("SMTP_USER", "")
    # Send a reminder this many days before each deadline (0 = on the day).
    REMINDER_OFFSETS_DAYS = (3, 1, 0)

    # --- Scraping politeness ---
    USER_AGENT_CONTACT = os.getenv("USER_AGENT_CONTACT", "unknown")
    REQUEST_DELAY_SECONDS = _float("REQUEST_DELAY_SECONDS", 2.0)
    REQUEST_TIMEOUT_SECONDS = _int("REQUEST_TIMEOUT_SECONDS", 25)
    MAX_DOWNLOAD_BYTES = 15 * 1024 * 1024  # 15 MB
    MAX_PDF_PAGES = 12
    # Re-download notices younger than this many days to spot in-place revisions.
    RECHECK_DAYS = _int("RECHECK_DAYS", 14)

    @classmethod
    def user_agent(cls) -> str:
        return f"NoticeNestBot/1.0 (student project; contact: {cls.USER_AGENT_CONTACT})"
