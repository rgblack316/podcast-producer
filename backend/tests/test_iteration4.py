"""Iteration 4: Setup wizard, Backup/Restore, Series episodes membership, Dashboard Upcoming."""
import io
import os
import json
import zipfile
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
if not BASE_URL:
    # load from frontend .env
    try:
        with open("/app/frontend/.env") as _f:
            for _ln in _f:
                if _ln.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = _ln.split("=", 1)[1].strip().strip('"').rstrip("/")
                    break
    except FileNotFoundError:
        pass
API = f"{BASE_URL}/api"
ADMIN_USER = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASS = os.environ["ADMIN_PASSWORD"]


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, r.text
    yield s


@pytest.fixture(scope="module")
def producer(admin):
    uname = f"it4_prod_x1"
    pwd = "ProdPass!1"
    # idempotent create
    existing = [u for u in admin.get(f"{API}/users").json() if u["username"] == uname]
    if not existing:
        r = admin.post(f"{API}/users", json={"username": uname, "name": "it4", "password": pwd, "role": "producer"})
        assert r.status_code == 200, r.text
        uid = r.json()["id"]
    else:
        uid = existing[0]["id"]
        admin.patch(f"{API}/users/{uid}", json={"active": True})
        admin.post(f"{API}/users/{uid}/reset-password", json={"new_password": pwd})
    s = requests.Session()
    rr = s.post(f"{API}/auth/login", json={"username": uname, "password": pwd})
    assert rr.status_code == 200
    yield s
    admin.patch(f"{API}/users/{uid}", json={"active": False})


# ---------- SETUP STATUS ----------
class TestSetupStatus:
    def test_status_shows_no_setup_needed(self):
        r = requests.get(f"{API}/setup/status")
        assert r.status_code == 200
        d = r.json()
        assert d["needs_setup"] is False
        assert d["token_required"] is False  # SETUP_TOKEN not set

    def test_setup_blocked_when_users_exist(self):
        r = requests.post(f"{API}/setup", json={
            "admin": {"username": "shouldfail", "name": "x", "password": "AbcDef12!"},
            "podcast": {"show_name": "nope"},
        })
        assert r.status_code == 409

    def test_setup_restore_blocked_when_users_exist(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("manifest.json", json.dumps({"app": "bible-bytes-producer", "version": 1}))
        buf.seek(0)
        r = requests.post(f"{API}/setup/restore", files={"file": ("x.zip", buf.getvalue(), "application/zip")})
        assert r.status_code == 409


# ---------- BACKUP ----------
class TestBackup:
    def test_producer_cannot_download(self, producer):
        r = producer.get(f"{API}/backup")
        assert r.status_code == 403

    def test_admin_downloads_valid_zip(self, admin):
        r = admin.get(f"{API}/backup")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/zip")
        z = zipfile.ZipFile(io.BytesIO(r.content))
        names = z.namelist()
        assert "manifest.json" in names
        manifest = json.loads(z.read("manifest.json"))
        assert manifest["app"] == "bible-bytes-producer"
        for c in ("users", "episodes", "documents", "settings", "series", "plan_items", "rss_items", "coverage_suggestions"):
            assert f"db/{c}.json" in names, f"missing db/{c}.json"
        users = json.loads(z.read("db/users.json"))
        assert any(u.get("role") == "admin" and u.get("username") == "admin" for u in users)
        # stash for restore test
        with open("/tmp/bb_backup_it4.zip", "wb") as f:
            f.write(r.content)


# ---------- RESTORE VALIDATION ----------
class TestRestoreValidation:
    def test_restore_invalid_zip(self, admin):
        r = admin.post(f"{API}/backup/restore", files={"file": ("x.zip", b"not a zip", "application/zip")})
        assert r.status_code == 400

    def test_restore_zip_wrong_app(self, admin):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("manifest.json", json.dumps({"app": "something-else"}))
        r = admin.post(f"{API}/backup/restore", files={"file": ("x.zip", buf.getvalue(), "application/zip")})
        assert r.status_code == 400

    def test_restore_zip_no_admin_user(self, admin):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("manifest.json", json.dumps({"app": "bible-bytes-producer", "version": 1}))
            z.writestr("db/users.json", json.dumps([{"username": "u", "role": "producer"}]))
        r = admin.post(f"{API}/backup/restore", files={"file": ("x.zip", buf.getvalue(), "application/zip")})
        assert r.status_code == 400
        assert "admin" in r.json()["detail"].lower()


# ---------- SERIES EPISODE MEMBERSHIP ----------
class TestSeriesMembership:
    def test_add_remove_episode_to_series(self, admin):
        # create series
        s1 = admin.post(f"{API}/series", json={"name": "TEST_IT4_SeriesA", "color": "#AA3344"}).json()
        s2 = admin.post(f"{API}/series", json={"name": "TEST_IT4_SeriesB", "color": "#1A2B3C"}).json()
        # create a published episode
        ep = admin.post(f"{API}/episodes", json={
            "title": "TEST_IT4_Ep1", "episode_number": "E1", "topic": "t",
            "primary_scripture": "John 10:11", "supporting_scriptures": [], "themes": [],
            "target_length": "", "audience_notes": "", "guidance": ""}).json()
        ep_id = ep["id"]
        # set published_at via status change
        admin.patch(f"{API}/episodes/{ep_id}/status", json={"status": "published"})

        # add to series A -> creates plan item
        r = admin.post(f"{API}/series/{s1['id']}/episodes", json={"episode_ids": [ep_id]})
        assert r.status_code == 200
        assert r.json()["added"] == 1

        mem = admin.get(f"{API}/series/membership").json()
        assert mem.get(ep_id) == s1["id"]

        # add same episode to series B -> moves (still single plan item)
        r2 = admin.post(f"{API}/series/{s2['id']}/episodes", json={"episode_ids": [ep_id]})
        assert r2.status_code == 200
        mem2 = admin.get(f"{API}/series/membership").json()
        assert mem2.get(ep_id) == s2["id"]
        # verify only ONE plan item for the ep
        plans = admin.get(f"{API}/plan").json()
        matching = [p for p in plans if p.get("episode_id") == ep_id]
        assert len(matching) == 1

        # remove episode from series
        r3 = admin.post(f"{API}/series/remove-episodes", json={"episode_ids": [ep_id]})
        assert r3.status_code == 200
        mem3 = admin.get(f"{API}/series/membership").json()
        assert ep_id not in mem3

        # bad series id
        r4 = admin.post(f"{API}/series/nope/episodes", json={"episode_ids": [ep_id]})
        assert r4.status_code == 404

        # cleanup
        for p in matching:
            admin.delete(f"{API}/plan/{p['id']}")
        admin.delete(f"{API}/series/{s1['id']}")
        admin.delete(f"{API}/series/{s2['id']}")
        admin.delete(f"{API}/episodes/{ep_id}")


# ---------- PODCAST INFO (settings) ----------
class TestPodcastInfoSettings:
    def test_save_and_retrieve_podcast_fields(self, admin):
        payload = {
            "show_tagline": "TEST_IT4 tagline",
            "host_names": "Alice & Bob",
            "show_description": "A test description",
            "audience": "Testers",
        }
        r = admin.put(f"{API}/settings", json=payload)
        assert r.status_code == 200
        got = r.json()
        for k, v in payload.items():
            assert got[k] == v
        # verify public (producers)
        pub = admin.get(f"{API}/settings/public").json()
        for k, v in payload.items():
            assert pub[k] == v


# ---------- Dashboard "Upcoming" (via /plan endpoint) ----------
class TestUpcomingPanelData:
    """Server-side logic is in frontend UpcomingPanel.js. We verify /plan returns dates
    within [-60, +60] window with hydrated episode info — which the panel uses to flag."""
    def test_plan_range_filter_and_hydration(self, admin):
        today = datetime.now(timezone.utc).date()
        d_yesterday = (today - timedelta(days=1)).isoformat()
        d_in5 = (today + timedelta(days=5)).isoformat()
        d_in10 = (today + timedelta(days=10)).isoformat()
        d_in40 = (today + timedelta(days=40)).isoformat()

        # Create a draft episode and link to in-5-days plan
        draft_ep = admin.post(f"{API}/episodes", json={
            "title": "TEST_IT4_Draft", "episode_number": "D1", "topic": "x",
            "primary_scripture": "John 1:1", "supporting_scriptures": [], "themes": [],
            "target_length": "", "audience_notes": "", "guidance": ""}).json()
        p_overdue = admin.post(f"{API}/plan", json={"title": "TEST_IT4_Overdue", "date": d_yesterday}).json()
        p_behind = admin.post(f"{API}/plan", json={"episode_id": draft_ep["id"], "date": d_in5}).json()
        p_notstarted = admin.post(f"{API}/plan", json={"title": "TEST_IT4_Not", "date": d_in10}).json()
        p_ontrack = admin.post(f"{API}/plan", json={"title": "TEST_IT4_On", "date": d_in40}).json()

        start = (today - timedelta(days=60)).isoformat()
        end = (today + timedelta(days=60)).isoformat()
        plans = admin.get(f"{API}/plan", params={"start": start, "end": end}).json()
        ids = {p["id"] for p in plans}
        assert p_overdue["id"] in ids
        assert p_behind["id"] in ids
        assert p_notstarted["id"] in ids
        assert p_ontrack["id"] in ids

        # Linked plan has hydrated episode with status
        behind_row = [p for p in plans if p["id"] == p_behind["id"]][0]
        assert behind_row["episode"] is not None
        assert behind_row["episode"]["status"] == "draft"
        assert behind_row["episode"]["id"] == draft_ep["id"]

        # cleanup
        for pid in [p_overdue["id"], p_behind["id"], p_notstarted["id"], p_ontrack["id"]]:
            admin.delete(f"{API}/plan/{pid}")
        admin.delete(f"{API}/episodes/{draft_ep['id']}")


# ---------- Final cleanup ----------
def test_zz_cleanup(admin):
    for e in admin.get(f"{API}/episodes").json():
        if e["title"].startswith("TEST_IT4"):
            admin.delete(f"{API}/episodes/{e['id']}")
    for p in admin.get(f"{API}/plan").json():
        if p.get("title", "").startswith("TEST_IT4"):
            admin.delete(f"{API}/plan/{p['id']}")
    for s in admin.get(f"{API}/series").json():
        if s["name"].startswith("TEST_IT4"):
            admin.delete(f"{API}/series/{s['id']}")
    # clear the test tagline/etc so we leave settings tidy
    admin.put(f"{API}/settings", json={"show_tagline": "", "host_names": "", "show_description": "", "audience": ""})
    # ensure admin still works
    r = requests.post(f"{API}/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
    assert r.status_code == 200
