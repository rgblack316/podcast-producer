"""Run by test_app_smoke.py in a clean interpreter (the app binds its DB connection at import time)."""
import io
import os
import sys
import tempfile
import zipfile

os.environ.update(JWT_SECRET="s" * 40, DB_NAME="smoke", MONGO_URL="mongodb://unused",
                  MEDIA_DIR=tempfile.mkdtemp(), SETUP_TOKEN="tok", COOKIE_SECURE="false")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import motor.motor_asyncio as m  # noqa: E402
from mongomock_motor import AsyncMongoMockClient  # noqa: E402

m.AsyncIOMotorClient = lambda *a, **k: AsyncMongoMockClient()
from fastapi.testclient import TestClient  # noqa: E402
import server  # noqa: E402


def run(client):
    assert client.get("/api/health").status_code == 200
    st = client.get("/api/setup/status").json()
    assert st["needs_setup"] is True
    body = {"setup_token": "tok", "admin": {"username": "admin", "password": "correct horse 1"},
            "podcast": {"show_name": "Show"}, "ai": {"gemini_api_key": "gk-secret"}}
    assert client.post("/api/setup", json={**body, "setup_token": "nope"}).status_code in (401, 403)
    r = client.post("/api/setup", json=body)
    assert r.status_code == 200, r.text
    assert client.get("/api/auth/me").json()["username"] == "admin"
    # API key is stored encrypted but still usable
    s = client.get("/api/settings").json()
    assert s["gemini_api_key_masked"] and "gk-secret" not in str(s)
    # backup has no keys
    z = zipfile.ZipFile(io.BytesIO(client.get("/api/backup").content))
    assert "gk-secret" not in z.read("db/settings.json").decode() and "api_key" not in z.read("db/settings.json").decode()
    # logout revokes the session
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    # login works and wrong password fails
    assert client.post("/api/auth/login", json={"username": "admin", "password": "bad"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "admin", "password": "correct horse 1"}).status_code == 200
    assert client.get("/api/auth/me").status_code == 200
    # audit trail recorded the events, without secrets
    rows = client.get("/api/settings/audit").json()
    actions = [r["action"] for r in rows]
    for a in ("setup_completed", "backup_download", "logout", "login_failed", "login"):
        assert a in actions, (a, actions)
    assert "correct horse" not in str(rows) and "gk-secret" not in str(rows)


with TestClient(server.app) as c:
    run(c)
print("SMOKE OK")
