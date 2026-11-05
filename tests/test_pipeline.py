from pathlib import Path

from app.config import Config
from app.db import connection, now_iso
from app.jobs.run_once import run
from app.services import alerts

SAMPLE = """Title: Examination Form for BCA III Semester
Date: 20.10.2026
URL: https://demo.example.com/n/1
---
Last date for submission of examination form without late fee is 05.11.2026.
"""


def _folder(tmp_path, monkeypatch, text):
    folder = tmp_path / "samples"
    folder.mkdir()
    (folder / "n1.txt").write_text(text, encoding="utf-8")
    monkeypatch.setattr(Config, "BASE_DIR", tmp_path)
    (tmp_path / "config").mkdir()
    sources = tmp_path / "config" / "sources.yaml"
    sources.write_text("sources:\n  - name: T\n    kind: local\n    path: samples\n", encoding="utf-8")
    monkeypatch.setattr(Config, "SOURCES_FILE", sources)
    return folder / "n1.txt"


def test_new_then_unchanged_then_revised(temp_db, monkeypatch, tmp_path):
    f = _folder(tmp_path, monkeypatch, SAMPLE)
    assert run(send_reminders=False)["new"] == 1
    assert run(send_reminders=False)["unchanged"] == 1

    f.write_text(SAMPLE.replace("05.11.2026", "12.11.2026"), encoding="utf-8")
    assert run(send_reminders=False)["revised"] == 1
    with connection() as conn:
        change = conn.execute("SELECT summary FROM changes").fetchone()["summary"]
        assert "moved from 5 Nov 2026 to 12 Nov 2026" in change
        assert conn.execute("SELECT version FROM notices").fetchone()["version"] == 2


def test_matching_student_gets_reminders_and_other_course_does_not(temp_db, monkeypatch, tmp_path):
    with connection() as conn:
        for name, course in (("Asha", "BCA"), ("Ravi", "MBA")):
            conn.execute("INSERT INTO users (name,email,token,course,semester,created_at) VALUES (?,?,?,?,3,?)",
                         (name, f"{name}@x.com", name, course, now_iso()))
    _folder(tmp_path, monkeypatch, SAMPLE)
    run(send_reminders=False)
    with connection() as conn:
        by_user = {r["name"]: r["c"] for r in conn.execute(
            "SELECT u.name, COUNT(*) c FROM alerts a JOIN users u ON u.id=a.user_id GROUP BY u.name")}
    assert "Asha" in by_user and "Ravi" not in by_user


def test_due_reminders_are_sent_once(temp_db, monkeypatch, tmp_path):
    from datetime import date
    with connection() as conn:
        conn.execute("INSERT INTO users (name,email,token,course,semester,created_at) VALUES ('Asha','a@x.com','t','BCA',3,?)",
                     (now_iso(),))
    _folder(tmp_path, monkeypatch, SAMPLE)
    run(send_reminders=False)
    with connection() as conn:
        first = alerts.process_due_alerts(conn, today=date(2026, 11, 2))     # 3 days before 5 Nov
        again = alerts.process_due_alerts(conn, today=date(2026, 11, 2))
    assert first["sent"] == 1 and again["sent"] == 0
