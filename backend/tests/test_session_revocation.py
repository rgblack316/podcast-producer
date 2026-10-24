"""Session revocation: password change/reset/deactivation/logout invalidate tokens. Pure unit tests, no Mongo needed."""
import asyncio
import os
import re

import pytest

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "unit_test")
os.environ.setdefault("JWT_SECRET", "x" * 32)
os.environ.setdefault("MEDIA_DIR", "/tmp/podcast-producer-unit-media")
os.environ["COOKIE_SECURE"] = "false"

from fastapi import HTTPException, Response  # noqa: E402
from starlette.requests import Request  # noqa: E402

import audit as audit_mod  # noqa: E402
import auth  # noqa: E402


class Col:
    """Tiny in-memory stand-in for a Motor collection (equality / $in queries, $set / $inc, upsert)."""
    def __init__(self):
        self.docs = []

    @staticmethod
    def _match(d, q):
        for k, v in q.items():
            if isinstance(v, dict) and "$in" in v:
                if d.get(k) not in v["$in"]:
                    return False
            elif isinstance(v, dict) and "$ne" in v:
                if d.get(k) == v["$ne"]:
                    return False
            elif d.get(k) != v:
                return False
        return True

    @staticmethod
    def _project(d, proj):
        d = dict(d)
        if proj:
            if any(v == 1 for k, v in proj.items() if k != "_id"):
                d = {k: v for k, v in d.items() if proj.get(k) == 1}
            else:
                d = {k: v for k, v in d.items() if proj.get(k, 1) != 0}
        return d

    async def find_one(self, q, proj=None):
        for d in self.docs:
            if self._match(d, q):
                return self._project(d, proj)
        return None

    async def insert_one(self, doc):
        self.docs.append(dict(doc))

    async def update_one(self, q, u, upsert=False):
        for d in self.docs:
            if self._match(d, q):
                break
        else:
            if not upsert:
                return type("R", (), {"matched_count": 0})()
            d = dict(q)
            self.docs.append(d)
        d.update(u.get("$set", {}))
        for k, v in u.get("$inc", {}).items():
            d[k] = d.get(k, 0) + v
        return type("R", (), {"matched_count": 1})()

    async def delete_many(self, q):
        self.docs = [d for d in self.docs if not self._match(d, q)]


class DB:
    def __init__(self):
        self.users, self.login_attempts, self.revoked_tokens, self.audit_log = Col(), Col(), Col(), Col()


def req(cookies=None):
    hdr = [(b"cookie", "; ".join(f"{k}={v}" for k, v in (cookies or {}).items()).encode())] if cookies else []
    return Request({"type": "http", "scheme": "http", "server": ("h", 80), "path": "/", "headers": hdr,
                    "query_string": b"", "client": ("1.2.3.4", 1)})


def cookies_from(resp):
    out = {}
    for k, v in resp.raw_headers:
        if k == b"set-cookie":
            m = re.match(r"(\w+)=([^;]*)", v.decode())
            out[m.group(1)] = m.group(2)
    return out


def run(c):
    return asyncio.run(c)


@pytest.fixture
def world(monkeypatch):
    db = DB()
    monkeypatch.setattr(auth, "db", db)
    monkeypatch.setattr(audit_mod, "db", db)
    run(db.users.insert_one(auth.user_doc("bob", "Bob", "old-password", "producer")))
    run(db.users.insert_one(auth.user_doc("root", "Root", "root-password", "admin")))
    return db


def login(username="bob", password="old-password"):
    resp = Response()
    run(auth.login(auth.LoginIn(username=username, password=password), req(), resp))
    return cookies_from(resp)


def me(cookies):
    return run(auth.get_current_user(req({"access_token": cookies["access_token"]})))


def refresh(cookies):
    resp = Response()
    run(auth.refresh(req({"refresh_token": cookies["refresh_token"]}), resp))
    return cookies_from(resp)


def status_of(fn, *a):
    try:
        fn(*a)
        return 200
    except HTTPException as e:
        return e.status_code


def test_login_session_works_and_hides_token_version(world):
    c = login()
    user = me(c)
    assert user["username"] == "bob" and "token_version" not in user and "password_hash" not in user
    assert me(refresh(c))["username"] == "bob"   # refresh issues working cookies


def test_legacy_tokens_and_users_without_version_still_work(world):
    bob = run(world.users.find_one({"username": "bob"}))
    world.users.docs[0].pop("token_version", None)
    legacy = auth.jwt.encode({"sub": bob["id"], "type": "access",
                              "exp": auth.datetime.now(auth.timezone.utc) + auth.timedelta(minutes=5)},
                             os.environ["JWT_SECRET"], algorithm="HS256")
    assert me({"access_token": legacy})["username"] == "bob"


def test_changing_own_password_signs_out_other_sessions_but_keeps_this_one(world):
    phone, laptop = login(), login()
    resp = Response()
    bob = me(laptop)
    run(auth.change_password(auth.ChangePasswordIn(current_password="old-password", new_password="new-password-1"),
                             req({"access_token": laptop["access_token"]}), resp, bob))
    fresh = cookies_from(resp)
    assert status_of(me, phone) == 401 and status_of(refresh, phone) == 401   # other device signed out
    assert status_of(me, laptop) == 401                                      # old tokens of this session too
    assert me(fresh)["username"] == "bob"                                    # but the new cookies work
    assert status_of(login, "bob", "old-password") == 401
    assert login("bob", "new-password-1")


def test_admin_reset_password_signs_the_user_out(world):
    c = login()
    bob_id = world.users.docs[0]["id"]
    run(auth.reset_password(bob_id, auth.ResetPasswordIn(new_password="reset-pass-1"), None, {"id": "x"}))
    assert status_of(me, c) == 401 and status_of(refresh, c) == 401


def test_deactivation_kills_tokens_even_after_reactivation(world):
    c = login()
    bob_id = world.users.docs[0]["id"]
    admin = {"id": world.users.docs[1]["id"]}
    run(auth.update_user(bob_id, auth.UserUpdate(active=False), None, admin))
    assert status_of(me, c) == 401
    run(auth.update_user(bob_id, auth.UserUpdate(active=True), None, admin))
    assert status_of(me, c) == 401            # reactivating must not resurrect the old session
    assert me(login())["username"] == "bob"   # a fresh sign-in works


def test_logout_revokes_that_session_only(world):
    a, b = login(), login()
    run(auth.logout(req({"access_token": a["access_token"], "refresh_token": a["refresh_token"]}), Response()))
    assert status_of(me, a) == 401 and status_of(refresh, a) == 401
    assert me(b)["username"] == "bob"          # the other device is untouched


def test_forged_or_garbage_tokens_are_rejected(world):
    assert status_of(me, {"access_token": "not-a-token"}) == 401
    bad = auth.jwt.encode({"sub": "x", "type": "access", "tv": 0,
                           "exp": auth.datetime.now(auth.timezone.utc) + auth.timedelta(minutes=5)}, "other-secret", algorithm="HS256")
    assert status_of(me, {"access_token": bad}) == 401
