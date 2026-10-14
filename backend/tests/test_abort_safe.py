"""Safe isolated test of early-abort on auth error. Snapshots, mutates, restores.

Guard: Even though conftest's session-scope autouse fixture will restore everything
after pytest exits, this test ALSO does its own targeted restore inside the test so
the DB is correct even if interrupted.
"""
import os
import time
import copy
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else "http://localhost:8001"
# Prefer public URL from frontend/.env
try:
    for line in Path("/app/frontend/.env").read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
except Exception:
    pass

ADMIN_USER = os.environ["ADMIN_USERNAME"]
ADMIN_PASS = os.environ["ADMIN_PASSWORD"]


@pytest.fixture(scope="module")
def db():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASS}, timeout=30)
    assert r.status_code == 200, r.text
    return s


def test_abort_on_auth_error(db, admin_session):
    # Snapshot settings and rss_jobs
    settings_before = copy.deepcopy(db.settings.find_one({"id": "app"}))
    assert settings_before is not None
    real_key = settings_before.get("gemini_api_key", "")
    real_key_len, real_key_last4 = len(real_key), real_key[-4:]
    jobs_before = list(db.rss_jobs.find({}))
    feed_url = settings_before.get("rss_feed_url") or ""

    # Insert 6 temp rss_items
    temp_guids = [f"TEST_ABORT_{i}" for i in range(6)]
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    temp_docs = []
    for i, g in enumerate(temp_guids):
        temp_docs.append({
            "id": g, "guid": g, "feed_url": feed_url,
            "title": f"Temp Abort {i}", "description": "Lorem ipsum content for abort test " * 30,
            "pub_date": now, "status": "new", "error": None, "content": None,
            "content_source": None, "suggestion": None, "audio_url": None,
            "transcript_url": None, "link": None, "created_at": now,
        })
    db.rss_items.insert_many(temp_docs)

    try:
        # Set fake key
        db.settings.update_one({"id": "app"}, {"$set": {"gemini_api_key": "fake-key-abort"}})

        # Trigger analyze on only our 6 ids
        r = admin_session.post(f"{BASE_URL}/api/rss/analyze", json={"ids": temp_guids, "provider": "gemini"}, timeout=30)
        assert r.status_code in (200, 202), r.text

        # Poll job for completion
        aborted_msg = None
        done = total = errors = 0
        for _ in range(60):
            time.sleep(1)
            job = db.rss_jobs.find_one({"id": "current"})
            if not job:
                continue
            if not job.get("running"):
                aborted_msg = job.get("aborted")
                done = job.get("done", 0)
                total = job.get("total", 0)
                errors = job.get("errors", 0)
                break
        print(f"Job finished: running=False total={total} done={done} errors={errors} aborted={aborted_msg}")
        assert aborted_msg, "Expected job.aborted to be set"
        assert errors < 6, f"Expected early abort => errors<6, got {errors}"

        # Verify remaining items (status still 'new', no error) existed
        items = list(db.rss_items.find({"id": {"$in": temp_guids}}))
        unerrored = [it for it in items if not it.get("error")]
        print(f"Items with no error after abort: {len(unerrored)}/6")
        assert len(unerrored) >= 1, "Expected at least one item untouched after early abort"
    finally:
        # Cleanup temp items
        db.rss_items.delete_many({"id": {"$in": temp_guids}})
        # Restore real key exactly
        db.settings.update_one({"id": "app"}, {"$set": {"gemini_api_key": real_key}})
        # Restore rss_jobs exactly
        db.rss_jobs.delete_many({})
        if jobs_before:
            db.rss_jobs.insert_many(jobs_before)

    # Final verify
    s_after = db.settings.find_one({"id": "app"})
    gk = s_after.get("gemini_api_key", "")
    assert len(gk) == real_key_len and gk[-4:] == real_key_last4, "Real key was not restored!"


def test_ui_aborted_job_display(db, admin_session):
    """Set rss_jobs to an aborted state and verify UI endpoint returns the aborted message."""
    jobs_before = list(db.rss_jobs.find({}))
    try:
        db.rss_jobs.update_one(
            {"id": "current"},
            {"$set": {"running": False, "total": 10, "done": 3, "errors": 3,
                      "aborted": "Gemini error 400: API key not valid"}},
            upsert=True,
        )
        r = admin_session.get(f"{BASE_URL}/api/rss/job", timeout=15)
        assert r.status_code == 200, r.text
        j = r.json()
        print(f"GET /api/rss/job -> {j}")
        assert j.get("aborted") == "Gemini error 400: API key not valid"
        assert j.get("running") is False
        assert j.get("errors") == 3
    finally:
        db.rss_jobs.delete_many({})
        if jobs_before:
            db.rss_jobs.insert_many(jobs_before)
