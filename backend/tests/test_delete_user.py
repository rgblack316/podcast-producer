"""Backend tests for DELETE /api/users/{id}.

Creates its own qa_del_* producers and never touches pre-existing users.
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_USER = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASS = os.environ["ADMIN_PASSWORD"]


def _login(session: requests.Session, username: str, password: str) -> requests.Response:
    return session.post(f"{API}/auth/login", json={"username": username, "password": password})


@pytest.fixture
def admin_session():
    s = requests.Session()
    r = _login(s, ADMIN_USER, ADMIN_PASS)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    yield s


@pytest.fixture
def created_users(admin_session):
    """Track qa_del_ users we create and clean them up at the end."""
    created = []
    def _mk(role="producer", prefix="qa_del"):
        uname = f"{prefix}_{uuid.uuid4().hex[:8]}"
        r = admin_session.post(f"{API}/users", json={
            "username": uname, "name": uname, "password": "Testpass123!", "role": role,
        })
        assert r.status_code == 200, r.text
        data = r.json()
        created.append(data)
        return data
    yield _mk
    # cleanup: best-effort delete anything still present
    for u in created:
        try:
            admin_session.delete(f"{API}/users/{u['id']}")
        except Exception:
            pass


# Login works and admin is current ----------------------------------------------
def test_admin_login_and_me(admin_session):
    r = admin_session.get(f"{API}/auth/me")
    assert r.status_code == 200
    assert r.json()["username"] == "admin"
    assert r.json()["role"] == "admin"


# DELETE as producer -> 403 -----------------------------------------------------
def test_delete_requires_admin(admin_session, created_users):
    victim = created_users(role="producer")
    other = created_users(role="producer")
    # login as `other` producer in a fresh session
    s = requests.Session()
    r = _login(s, other["username"], "Testpass123!")
    assert r.status_code == 200
    r = s.delete(f"{API}/users/{victim['id']}")
    assert r.status_code == 403
    # victim must still exist
    r = admin_session.get(f"{API}/users")
    assert any(u["id"] == victim["id"] for u in r.json())


# Delete self -> 400 ------------------------------------------------------------
def test_delete_self_forbidden(admin_session):
    me = admin_session.get(f"{API}/auth/me").json()
    r = admin_session.delete(f"{API}/users/{me['id']}")
    assert r.status_code == 400
    assert "own account" in r.json()["detail"].lower()


# Delete non-existent -> 404 ---------------------------------------------------
def test_delete_missing_user(admin_session):
    r = admin_session.delete(f"{API}/users/does-not-exist-xyz")
    assert r.status_code == 404


# Delete real producer: session invalid + cannot re-login -----------------------
def test_delete_producer_invalidates_session_and_login(admin_session, created_users):
    victim = created_users(role="producer")
    # Victim logs in
    vs = requests.Session()
    r = _login(vs, victim["username"], "Testpass123!")
    assert r.status_code == 200
    # Admin deletes victim
    r = admin_session.delete(f"{API}/users/{victim['id']}")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    # Existing cookie now invalid
    r = vs.get(f"{API}/auth/me")
    assert r.status_code == 401
    # Fresh login fails
    r = _login(requests.Session(), victim["username"], "Testpass123!")
    assert r.status_code == 401
    # And the user is really gone
    r = admin_session.get(f"{API}/users")
    assert all(u["id"] != victim["id"] for u in r.json())


# Last-admin guard --------------------------------------------------------------
def test_last_admin_guard(admin_session, created_users):
    """
    We only exercise the guard against a qa_del admin -- NEVER against seeded admins.
    So we count other active admins first. If >= 1, deleting a qa_del admin should succeed.
    If == 0 we would skip, but the pre-existing admin satisfies this already.
    """
    me = admin_session.get(f"{API}/auth/me").json()
    users = admin_session.get(f"{API}/users").json()
    other_active_admins = [u for u in users if u["role"] == "admin" and u.get("active", True) and u["id"] != me["id"]]
    # Create a qa_del_ admin
    qa_admin = created_users(role="admin", prefix="qa_del_admin")
    # Since seeded `admin` is active admin != qa_admin, deletion should succeed.
    r = admin_session.delete(f"{API}/users/{qa_admin['id']}")
    assert r.status_code == 200, r.text
