"""Iteration 6: RSS feed artwork + show notes sync + Episode Series panel."""
import asyncio
import os
import sys
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else None
if not BASE_URL:
    load_dotenv("/app/frontend/.env")
    BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")

ADMIN = {"username": os.environ.get("ADMIN_USERNAME", "admin"), "password": os.environ["ADMIN_PASSWORD"]}


# ------------------------------- fixtures -------------------------------

@pytest.fixture(scope="module")
def admin_client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def producer_client(admin_client):
    # Create a temp producer user
    uname = "TEST_producer_i6"
    # list first
    users = admin_client.get(f"{BASE_URL}/api/users").json()
    existing = next((u for u in users if u.get("username") == uname), None)
    if not existing:
        r = admin_client.post(f"{BASE_URL}/api/users",
                              json={"username": uname, "password": "Prod!2026ab", "role": "producer"})
        assert r.status_code in (200, 201), r.text
        user_id = r.json().get("id")
    else:
        user_id = existing["id"]
        admin_client.post(f"{BASE_URL}/api/users/{user_id}/reset-password",
                          json={"password": "Prod!2026ab"})
    ps = requests.Session()
    r = ps.post(f"{BASE_URL}/api/auth/login", json={"username": uname, "password": "Prod!2026ab"})
    assert r.status_code == 200, r.text
    yield ps
    # cleanup
    try:
        admin_client.delete(f"{BASE_URL}/api/users/{user_id}")
    except Exception:
        pass


@pytest.fixture(scope="module")
def imported_episodes(admin_client):
    """Return the 2 real episodes with rss_guid."""
    r = admin_client.get(f"{BASE_URL}/api/episodes")
    assert r.status_code == 200
    eps = [e for e in r.json() if e.get("rss_guid")]
    assert len(eps) >= 2, "expected 2 real imported episodes with rss_guid"
    return eps


# ----------------------- 1. sync-imported idempotency -----------------------

class TestSyncImported:
    def test_sync_imported_returns_totals(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/rss/sync-imported",
                              json={"artwork": True, "show_notes": True}, timeout=120)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "episodes" in d and "artwork" in d and "show_notes" in d
        assert d["episodes"] >= 2

    def test_sync_imported_does_not_duplicate_artwork(self, admin_client, imported_episodes):
        # Snapshot current artwork counts
        before = {}
        for e in imported_episodes:
            full = admin_client.get(f"{BASE_URL}/api/episodes/{e['id']}").json()
            before[e["id"]] = len((full.get("artwork") or {}).get("images") or [])
        # Re-run sync
        r = admin_client.post(f"{BASE_URL}/api/rss/sync-imported",
                              json={"artwork": True, "show_notes": True}, timeout=120)
        assert r.status_code == 200
        assert r.json()["artwork"] == 0, "artwork should not be re-downloaded"
        # Verify counts unchanged
        for ep_id, cnt in before.items():
            full = admin_client.get(f"{BASE_URL}/api/episodes/{ep_id}").json()
            now_cnt = len((full.get("artwork") or {}).get("images") or [])
            assert now_cnt == cnt, f"artwork count changed on {ep_id}: {cnt} -> {now_cnt}"

    def test_episodes_have_feed_artwork_and_show_notes(self, admin_client, imported_episodes):
        for e in imported_episodes:
            full = admin_client.get(f"{BASE_URL}/api/episodes/{e['id']}").json()
            imgs = (full.get("artwork") or {}).get("images") or []
            assert any(i.get("provider") == "rss" for i in imgs), f"no rss artwork for {e['id']}"
            selected = (full.get("artwork") or {}).get("selected_image_id")
            assert selected, f"no selected image for {e['id']}"
            assets = full.get("assets") or {}
            assert assets.get("show_notes"), f"no show notes for {e['id']}"
            # source should be rss (not manual) at this baseline
            assert assets.get("source") in ("rss", "manual", None)


# ----------------------- 2. Per-episode sync endpoint -----------------------

class TestPerEpisodeSync:
    def test_sync_artwork_already_in_gallery(self, admin_client, imported_episodes):
        ep = imported_episodes[0]
        r = admin_client.post(f"{BASE_URL}/api/rss/episode/{ep['id']}/sync",
                              json={"artwork": True, "show_notes": False}, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["artwork"] is False  # already present
        assert d["show_notes"] is False

    def test_sync_show_notes_overwrites_rss_source(self, admin_client, imported_episodes):
        ep = imported_episodes[0]
        r = admin_client.post(f"{BASE_URL}/api/rss/episode/{ep['id']}/sync",
                              json={"artwork": False, "show_notes": True}, timeout=60)
        assert r.status_code == 200, r.text
        # source is rss -> allowed to re-apply
        assert r.json()["show_notes"] is True

    def test_manual_edit_prevents_overwrite(self, admin_client, imported_episodes):
        ep = imported_episodes[1]
        # First save notes manually (PUT sets source=manual)
        full = admin_client.get(f"{BASE_URL}/api/episodes/{ep['id']}").json()
        current_assets = full.get("assets") or {}
        original_notes = current_assets.get("show_notes", "")
        edited = (original_notes or "") + "\n\n**TEST_edit_marker**"
        r = admin_client.put(f"{BASE_URL}/api/episodes/{ep['id']}/assets", json={
            "show_notes": edited,
            "description": current_assets.get("description", ""),
            "social_posts": current_assets.get("social_posts", ""),
        })
        assert r.status_code == 200, r.text
        # confirm source=manual
        after = admin_client.get(f"{BASE_URL}/api/episodes/{ep['id']}").json()
        assert (after.get("assets") or {}).get("source") == "manual"
        # Now sync -> show_notes should NOT be overwritten
        r = admin_client.post(f"{BASE_URL}/api/rss/episode/{ep['id']}/sync",
                              json={"artwork": False, "show_notes": True}, timeout=60)
        assert r.status_code == 200
        assert r.json()["show_notes"] is False, "edited manual notes must not be overwritten"
        # confirm the marker is still there
        after2 = admin_client.get(f"{BASE_URL}/api/episodes/{ep['id']}").json()
        assert "TEST_edit_marker" in (after2.get("assets") or {}).get("show_notes", "")
        # Restore original (so final state is as before)
        admin_client.put(f"{BASE_URL}/api/episodes/{ep['id']}/assets", json={
            "show_notes": original_notes,
            "description": current_assets.get("description", ""),
            "social_posts": current_assets.get("social_posts", ""),
        })
        # Re-sync to put source back to rss for cleanliness
        admin_client.post(f"{BASE_URL}/api/rss/episode/{ep['id']}/sync",
                          json={"artwork": False, "show_notes": True})

    def test_sync_rejects_non_rss_episode(self, admin_client):
        # Find an episode without rss_guid
        eps = admin_client.get(f"{BASE_URL}/api/episodes").json()
        non_rss = next((e for e in eps if not e.get("rss_guid")), None)
        assert non_rss is not None, "need a non-rss episode"
        r = admin_client.post(f"{BASE_URL}/api/rss/episode/{non_rss['id']}/sync",
                              json={"artwork": True, "show_notes": True})
        assert r.status_code == 400, r.text

    def test_sync_producer_role_forbidden(self, producer_client, imported_episodes):
        ep = imported_episodes[0]
        r = producer_client.post(f"{BASE_URL}/api/rss/episode/{ep['id']}/sync",
                                 json={"artwork": True, "show_notes": True})
        assert r.status_code == 403, r.text


# ----------------------- 3. parse_feed + sync_episode_from_feed (fixture) -----------------------

class TestFixtureParseAndSync:
    def test_parse_feed_captures_image_and_summary(self):
        import rss_import
        xml = Path("/app/tests/rss_fixture/feed_art.xml").read_bytes()
        items = rss_import.parse_feed(xml)
        assert items, "feed should parse"
        ep3 = next((i for i in items if i["guid"] == "bb-test-3"), None)
        assert ep3, "ep3 should be in parsed items"
        assert ep3["image_url"] == "http://localhost:8099/art.png"
        assert "short summary of ep 3" in ep3["summary"].lower()

    def test_sync_episode_from_feed_png_contenttype(self, admin_client):
        """Create a temp episode, call sync_episode_from_feed via python, verify artwork endpoint returns image/png."""
        import rss_import
        from core import db, new_id, now_iso
        from pathlib import Path as _P
        import shutil

        ep_id = new_id()
        temp_ep = {
            "id": ep_id, "title": "TEST_i6_temp", "status": "published",
            "created_at": now_iso(), "created_by": "admin", "rss_guid": "TEST_i6_guid",
        }

        async def run():
            await db.episodes.insert_one(temp_ep)
            fake_item = {
                "image_url": "http://localhost:8099/art.png",
                "description": "TEST notes body",
                "summary": "TEST summary",
                "title": "TEST_i6_temp",
            }
            res = await rss_import.sync_episode_from_feed(ep_id, fake_item, {"username": "admin"})
            return res

        res = asyncio.run(run())
        assert res["artwork"] is True
        assert res["show_notes"] is True

        try:
            # Fetch episode, check artwork image and content-type
            full = admin_client.get(f"{BASE_URL}/api/episodes/{ep_id}").json()
            imgs = (full.get("artwork") or {}).get("images") or []
            assert imgs, "artwork image should be saved"
            img = imgs[0]
            assert img["source_url"] == "http://localhost:8099/art.png"
            assert img["provider"] == "rss"
            # fetch artwork file
            r = admin_client.get(f"{BASE_URL}/api/episodes/{ep_id}/artwork/{img['id']}.png")
            assert r.status_code == 200, r.text
            assert r.headers.get("content-type", "").startswith("image/png")
            # assets
            assert full["assets"]["source"] == "rss"
            assert full["assets"]["show_notes"] == "TEST notes body"
            assert full["assets"]["description"] == "TEST summary"
        finally:
            # cleanup: delete episode + media folder (use pymongo to avoid async loop reuse)
            from pymongo import MongoClient
            MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]].episodes.delete_one({"id": ep_id})
            media = _P(os.environ["MEDIA_DIR"]) / ep_id
            if media.exists():
                shutil.rmtree(media, ignore_errors=True)


# ----------------------- 4. Episode Series panel endpoints -----------------------

class TestEpisodeSeries:
    def test_series_crud_and_membership(self, admin_client, imported_episodes):
        ep_id = imported_episodes[0]["id"]
        # list existing + remember
        existing_ids = {s["id"] for s in admin_client.get(f"{BASE_URL}/api/series").json()}
        # create series A
        rA = admin_client.post(f"{BASE_URL}/api/series", json={"name": "TEST_i6_SeriesA", "color": "#B45309"})
        assert rA.status_code in (200, 201), rA.text
        sA = rA.json()
        # create series B
        rB = admin_client.post(f"{BASE_URL}/api/series", json={"name": "TEST_i6_SeriesB", "color": "#1C1917"})
        assert rB.status_code in (200, 201), rB.text
        sB = rB.json()
        try:
            # add episode to A
            r = admin_client.post(f"{BASE_URL}/api/series/{sA['id']}/episodes",
                                  json={"episode_ids": [ep_id]})
            assert r.status_code == 200, r.text
            mem = admin_client.get(f"{BASE_URL}/api/series/membership").json()
            assert mem.get(ep_id) == sA["id"]
            # change to B
            r = admin_client.post(f"{BASE_URL}/api/series/{sB['id']}/episodes",
                                  json={"episode_ids": [ep_id]})
            assert r.status_code == 200
            mem = admin_client.get(f"{BASE_URL}/api/series/membership").json()
            assert mem.get(ep_id) == sB["id"]
            # remove
            r = admin_client.post(f"{BASE_URL}/api/series/remove-episodes",
                                  json={"episode_ids": [ep_id]})
            assert r.status_code == 200
            mem = admin_client.get(f"{BASE_URL}/api/series/membership").json()
            assert ep_id not in mem or not mem.get(ep_id)
        finally:
            # Delete test series only (never user's existing ones)
            for sid in (sA["id"], sB["id"]):
                if sid not in existing_ids:
                    admin_client.delete(f"{BASE_URL}/api/series/{sid}")
