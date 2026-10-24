"""COOKIE_SECURE=auto: Secure flag follows the request scheme. Pure unit tests, no Mongo needed."""
import os

import pytest

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "unit_test")
os.environ.setdefault("JWT_SECRET", "x" * 32)
os.environ.setdefault("MEDIA_DIR", "/tmp/podcast-producer-unit-media")

from fastapi import Response  # noqa: E402
from starlette.requests import Request  # noqa: E402

import auth  # noqa: E402


def req(scheme):
    return Request({"type": "http", "scheme": scheme, "server": ("h", 80), "path": "/", "headers": [], "query_string": b""})


@pytest.mark.parametrize("mode,scheme,expected", [
    ("auto", "https", True), ("auto", "http", False),
    ("true", "https", True), ("true", "http", True),
    ("false", "https", False), ("false", "http", False),
    ("AUTO", "https", True),
])
def test_cookie_secure_modes(monkeypatch, mode, scheme, expected):
    monkeypatch.setenv("COOKIE_SECURE", mode)
    assert auth._cookie_secure(req(scheme)) is expected


def test_default_without_env_is_secure(monkeypatch):
    monkeypatch.delenv("COOKIE_SECURE", raising=False)
    assert auth._cookie_secure(req("http")) is True


def test_set_auth_cookies_flag(monkeypatch):
    monkeypatch.setenv("COOKIE_SECURE", "auto")
    for scheme, has_secure in (("https", True), ("http", False)):
        resp = Response()
        auth.set_auth_cookies(resp, {"id": "u1"}, req(scheme))
        cookies = [v.decode() for k, v in resp.raw_headers if k == b"set-cookie"]
        assert len(cookies) == 2 and all(("Secure" in c) is has_secure for c in cookies), cookies
