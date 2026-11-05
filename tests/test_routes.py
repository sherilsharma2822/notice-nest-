import re

from app import create_app
from app.config import Config
from app.jobs.run_once import run


def _client(temp_db, monkeypatch):
    monkeypatch.setattr(Config, "DATA_DIR", temp_db)
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def _csrf(client):
    html = client.get("/profile").get_data(as_text=True)
    return re.search(r'name="csrf" value="([^"]+)"', html).group(1)


def test_pages_load_with_demo_data(temp_db, monkeypatch):
    run(send_reminders=False)
    client = _client(temp_db, monkeypatch)
    for path in ("/", "/about", "/changes", "/metrics", "/profile", "/health", "/notice/1"):
        assert client.get(path).status_code == 200, path
    assert client.get("/notice/9999").status_code == 404


def test_profile_flow_and_calendar(temp_db, monkeypatch):
    run(send_reminders=False)
    client = _client(temp_db, monkeypatch)
    token = _csrf(client)
    resp = client.post("/profile", data={"csrf": token, "name": "Asha Verma", "email": "asha@example.com",
                                         "course": "BCA", "semester": "3"}, follow_redirects=True)
    assert resp.status_code == 200 and b"Profile saved" in resp.data
    dashboard = client.get("/").get_data(as_text=True)
    assert "Hello, Asha" in dashboard
    ics = client.get("/calendar.ics")
    assert ics.status_code == 200 and b"BEGIN:VEVENT" in ics.data


def test_profile_rejects_bad_input_and_missing_csrf(temp_db, monkeypatch):
    client = _client(temp_db, monkeypatch)
    assert client.post("/profile", data={"name": "x"}).status_code == 400           # no CSRF token
    token = _csrf(client)
    bad = client.post("/profile", data={"csrf": token, "name": "", "email": "nope", "course": "XYZ", "semester": "99"})
    assert bad.status_code == 400 and b"valid email" in bad.data


def test_email_cannot_be_taken_over(temp_db, monkeypatch):
    client = _client(temp_db, monkeypatch)
    form = {"name": "Asha", "email": "asha@example.com", "course": "BCA", "semester": "3"}
    client.post("/profile", data={**form, "csrf": _csrf(client)})
    other = _client(temp_db, monkeypatch)                                          # a different browser
    resp = other.post("/profile", data={**form, "name": "Evil", "csrf": _csrf(other)})
    assert resp.status_code == 400 and b"already has a profile" in resp.data
