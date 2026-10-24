import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

import ratelimit
from media import is_image


class FakeCursor:
    def __init__(self, rows): self.rows = rows
    def sort(self, *_): self.rows = sorted(self.rows, key=lambda r: r["at"]); return self
    async def to_list(self, n): return self.rows[:n]


class FakeEvents:
    def __init__(self): self.rows = []
    def find(self, q, _proj=None):
        return FakeCursor([r for r in self.rows if r["user_id"] == q["user_id"] and r["at"] > q["at"]["$gt"]])
    async def insert_one(self, doc): self.rows.append(doc)


class FakeDB:
    def __init__(self): self.ai_events = FakeEvents()


@pytest.fixture
def fake(monkeypatch):
    d = FakeDB()
    monkeypatch.setattr(ratelimit, "db", d)
    monkeypatch.setenv("AI_ACTIONS_PER_HOUR", "3")
    return d


def run(user): return asyncio.run(ratelimit.ai_rate_limit(user))


def test_blocks_after_limit(fake):
    for _ in range(3): run({"id": "u1"})
    with pytest.raises(HTTPException) as e:
        run({"id": "u1"})
    assert e.value.status_code == 429 and int(e.value.headers["Retry-After"]) > 0


def test_limit_is_per_user(fake):
    for _ in range(3): run({"id": "u1"})
    assert run({"id": "u2"})["id"] == "u2"


def test_old_events_expire(fake):
    old = datetime.now(timezone.utc) - timedelta(hours=2)
    fake.ai_events.rows = [{"user_id": "u1", "at": old}] * 5
    assert run({"id": "u1"})["id"] == "u1"


def test_zero_disables(fake, monkeypatch):
    monkeypatch.setenv("AI_ACTIONS_PER_HOUR", "0")
    for _ in range(10): run({"id": "u1"})
    assert fake.ai_events.rows == []


def test_is_image():
    assert is_image(b"\x89PNG\r\n\x1a\n" + b"x" * 20)
    assert is_image(b"\xff\xd8\xff\xe0" + b"x" * 20)
    assert is_image(b"RIFF\x00\x00\x00\x00WEBPVP8 ")
    assert not is_image(b"<svg xmlns='http://www.w3.org/2000/svg'><script/></svg>")
    assert not is_image(b"<html>")
    assert not is_image(b"")
