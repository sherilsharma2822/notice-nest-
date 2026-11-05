"""Shared test setup: every test gets its own empty temporary database."""
import pytest

from app.config import Config
from app.db import init_db


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(Config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(Config, "LLM_PROVIDER", "none")
    init_db()
    return tmp_path
