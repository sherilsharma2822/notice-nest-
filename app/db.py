"""Tiny helpers around SQLite (Python's built-in database)."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from .config import Config

SCHEMA_FILE = Path(__file__).resolve().parent / "schema.sql"


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def get_conn(path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(path or Config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row          # lets us use row["title"] instead of row[3]
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def connection():
    """Open a connection, save (commit) on success, undo (rollback) on error, always close."""
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with connection() as conn:
        conn.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))


def upsert_source(conn: sqlite3.Connection, name: str, kind: str, location: str | None) -> int:
    conn.execute(
        "INSERT INTO sources (name, kind, location) VALUES (?, ?, ?) "
        "ON CONFLICT(name) DO UPDATE SET kind = excluded.kind, location = excluded.location",
        (name, kind, location),
    )
    row = conn.execute("SELECT id FROM sources WHERE name = ?", (name,)).fetchone()
    return int(row["id"])
