"""Iteration 2 backend tests: show notes (assets), coverage map, artwork studio, settings extras."""
import io
import os
import uuid
from pathlib import Path

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://scripture-scribe-hub.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
MEDIA_DIR = Path(os.environ.get("MEDIA_DIR", "/app/backend/media"))
ADMIN_USER = "admin"
ADMIN_PASS = "BibleBytes!2026"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200
    yield s
    # cleanup fake keys
    try:
        import pymongo
        c = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        db = c[os.environ.get("DB_NAME", "test_database")]
        db.settings.update_one({"id": "app"}, {"$set": {"gemini_api_key": "", "openai_api_key": ""}})
        db.coverage_suggestions.delete_many({})
        c.close()
    except Exception:
        pass


@pytest.fixture(scope="module")
def mongo_db():
    import pymongo
    c = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    yield c[os.environ.get("DB_NAME", "test_database")]
    c.close()


@pytest.fixture()
def episode(admin_session):
    body = {"title": f"TEST_IT2_{uuid.uuid4().hex[:6]}", "episode_number": "E200",
            "topic": "Hagar seen", "primary_scripture": "Genesis 16:7-14",
            "supporting_scriptures": [], "themes": ["Grace"],
            "target_length": "15m", "audience_notes": "", "guidance": ""}
    r = admin_session.post(f"{API}/episodes", json=body)
    assert r.status_code == 200
    ep = r.json()
    yield ep
    admin_session.delete(f"{API}/episodes/{ep['id']}")


# ---------- Settings: image provider + models ----------
class TestSettingsImage:
    def test_blank_key_preserved(self, admin_session):
        # Set a key
        admin_session.put(f"{API}/settings", json={"gemini_api_key": "preserve-me-123"})
        s = admin_session.get(f"{API}/settings").json()
        assert s["gemini_configured"] is True
        # Send blank key -> should be ignored
        r = admin_session.put(f"{API}/settings", json={"gemini_api_key": "", "openai_api_key": ""})
        assert r.status_code == 200
        assert r.json()["gemini_configured"] is True

    def test_image_provider_and_models_save_and_persist(self, admin_session):
        r = admin_session.put(f"{API}/settings", json={
            "image_provider": "openai",
            "gemini_image_model": "gemini-2.5-flash-image",
            "openai_image_model": "gpt-image-1",
        })
        assert r.status_code == 200
        d = r.json()
        assert d["image_provider"] == "openai"
        assert d["gemini_image_model"] == "gemini-2.5-flash-image"
        assert d["openai_image_model"] == "gpt-image-1"
        # Switch back and verify persistence via public endpoint
        r2 = admin_session.put(f"{API}/settings", json={"image_provider": "gemini"})
        assert r2.status_code == 200
        pub = admin_session.get(f"{API}/settings/public").json()
        assert pub["image_provider"] == "gemini"
        assert "gemini_image_model" in pub
        assert "openai_image_model" in pub

    def test_image_provider_invalid(self, admin_session):
        r = admin_session.put(f"{API}/settings", json={"image_provider": "midjourney"})
        assert r.status_code == 400


# ---------- Coverage ----------
class TestCoverage:
    def test_coverage_structure(self, admin_session, episode):
        r = admin_session.get(f"{API}/coverage")
        assert r.status_code == 200
        d = r.json()
        assert "books" in d and "themes" in d and "timeline" in d
        assert len(d["books"]) == 66
        ot = [b for b in d["books"] if b["testament"] == "OT"]
        nt = [b for b in d["books"] if b["testament"] == "NT"]
        assert len(ot) == 39
        assert len(nt) == 27
        # episode has Genesis -> book count > 0
        gen = next(b for b in d["books"] if b["name"] == "Genesis")
        assert gen["count"] >= 1
        assert any(e["id"] == episode["id"] for e in gen["episodes"])

    def test_suggest_without_key_returns_400(self, admin_session, mongo_db):
        mongo_db.settings.update_one({"id": "app"}, {"$set": {"gemini_api_key": "", "openai_api_key": ""}})
        r = admin_session.post(f"{API}/coverage/suggest", json={"provider": "gemini", "count": 3})
        assert r.status_code == 400
        assert "key" in r.text.lower()

    def test_suggest_with_fake_key_fails_gracefully(self, admin_session):
        admin_session.put(f"{API}/settings", json={"gemini_api_key": "fake-key-xyz"})
        r = admin_session.post(f"{API}/coverage/suggest", json={"provider": "gemini", "count": 3})
        assert r.status_code == 400
        assert "AI suggestion failed" in r.text or "failed" in r.text.lower()
        # clear
        import pymongo
        c = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        c[os.environ.get("DB_NAME", "test_database")].settings.update_one(
            {"id": "app"}, {"$set": {"gemini_api_key": ""}})
        c.close()

    def test_coverage_includes_persisted_suggestions(self, admin_session, mongo_db):
        from datetime import datetime
        mongo_db.coverage_suggestions.update_one(
            {"id": "latest"},
            {"$set": {
                "id": "latest",
                "items": [{"id": "s1", "title": "Test Idea", "topic": "Ruth loyalty",
                           "primary_scripture": "Ruth 1:16", "supporting_scriptures": [],
                           "themes": ["Loyalty"], "why": "gap"}],
                "created_at": datetime.utcnow().isoformat() + "Z",
            }},
            upsert=True,
        )
        r = admin_session.get(f"{API}/coverage")
        assert r.status_code == 200
        d = r.json()
        assert any(s["id"] == "s1" and s["title"] == "Test Idea" for s in d["suggestions"])


# ---------- Assets / show notes ----------
class TestAssets:
    def test_assets_locked_for_draft(self, admin_session, episode):
        r = admin_session.post(f"{API}/episodes/{episode['id']}/assets/generate",
                               json={"provider": "gemini"})
        assert r.status_code == 400
        assert "script" in r.text.lower() or "complete" in r.text.lower()

    def test_put_assets_persists(self, admin_session, episode):
        r = admin_session.put(f"{API}/episodes/{episode['id']}/assets",
                              json={"show_notes": "# Notes", "description": "desc",
                                    "social_posts": "## IG\nhi"})
        assert r.status_code == 200
        ep = r.json()
        assert ep["assets"]["show_notes"] == "# Notes"
        assert ep["assets"]["description"] == "desc"
        assert ep["assets"]["updated_by"] == "admin"
        # verify GET
        g = admin_session.get(f"{API}/episodes/{episode['id']}").json()
        assert g["assets"]["description"] == "desc"

    def test_generate_assets_no_key(self, admin_session, episode, mongo_db):
        # Advance episode to script_complete
        admin_session.put(f"{API}/episodes/{episode['id']}/outline", json={"content": "# O"})
        admin_session.post(f"{API}/episodes/{episode['id']}/status", json={"status": "outline_approved"})
        admin_session.put(f"{API}/episodes/{episode['id']}/script", json={"content": "## Script\nhi"})
        admin_session.post(f"{API}/episodes/{episode['id']}/status", json={"status": "script_complete"})
        mongo_db.settings.update_one({"id": "app"}, {"$set": {"gemini_api_key": "", "openai_api_key": ""}})
        r = admin_session.post(f"{API}/episodes/{episode['id']}/assets/generate",
                               json={"provider": "gemini"})
        # Backend starts task then errors in last_error. Accept 200+last_error OR 400.
        if r.status_code == 200:
            import time
            for _ in range(10):
                ep = admin_session.get(f"{API}/episodes/{episode['id']}").json()
                if not ep.get("generating"):
                    break
                time.sleep(1)
            assert ep.get("last_error")
        else:
            assert r.status_code == 400


# ---------- Artwork ----------
class TestArtwork:
    def test_brainstorm_without_key(self, admin_session, episode, mongo_db):
        mongo_db.settings.update_one({"id": "app"}, {"$set": {"gemini_api_key": "", "openai_api_key": ""}})
        r = admin_session.post(f"{API}/episodes/{episode['id']}/artwork/brainstorm",
                               json={"provider": "gemini", "notes": "mood"})
        assert r.status_code == 400

    def test_generate_empty_prompt(self, admin_session, episode):
        r = admin_session.post(f"{API}/episodes/{episode['id']}/artwork/generate",
                               json={"prompt": "   "})
        assert r.status_code == 400

    def test_generate_with_fake_key_surfaces_error(self, admin_session, episode):
        admin_session.put(f"{API}/settings", json={"gemini_api_key": "fake-xyz", "image_provider": "gemini"})
        r = admin_session.post(f"{API}/episodes/{episode['id']}/artwork/generate",
                               json={"prompt": "a sunset over Mt Sinai", "provider": "gemini"})
        assert r.status_code == 200
        ep = r.json()
        assert ep.get("art_generating") is not None or ep.get("art_error")
        import time
        for _ in range(15):
            cur = admin_session.get(f"{API}/episodes/{episode['id']}").json()
            if not cur.get("art_generating"):
                break
            time.sleep(1)
        assert cur.get("art_error")
        # clear
        import pymongo
        c = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        c[os.environ.get("DB_NAME", "test_database")].settings.update_one(
            {"id": "app"}, {"$set": {"gemini_api_key": ""}})
        c.close()

    def test_artwork_file_auth_required_and_served(self, admin_session, episode, mongo_db):
        ep_id = episode["id"]
        img_id = str(uuid.uuid4())
        folder = MEDIA_DIR / ep_id
        folder.mkdir(parents=True, exist_ok=True)
        png = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
               b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xff\xff?\x00"
               b"\x05\xfe\x02\xfe\xa6\x1a\xeb\xf3\x00\x00\x00\x00IEND\xaeB`\x82")
        (folder / f"{img_id}.png").write_bytes(png)
        from datetime import datetime
        mongo_db.episodes.update_one({"id": ep_id}, {"$set": {
            "artwork.images": [{"id": img_id, "prompt": "x", "provider": "gemini:test",
                                "created_by": "admin",
                                "created_at": datetime.utcnow().isoformat() + "Z"}],
            "artwork.messages": [], "artwork.concepts": [],
            "artwork.selected_image_id": img_id,
        }})
        # Unauthenticated 401
        r_unauth = requests.get(f"{API}/episodes/{ep_id}/artwork/{img_id}.png")
        assert r_unauth.status_code == 401
        # Authenticated OK
        r_auth = admin_session.get(f"{API}/episodes/{ep_id}/artwork/{img_id}.png")
        assert r_auth.status_code == 200
        assert r_auth.headers["content-type"] == "image/png"
        assert r_auth.content[:4] == b"\x89PNG"
        # Select endpoint
        r_sel = admin_session.post(f"{API}/episodes/{ep_id}/artwork/{img_id}/select")
        assert r_sel.status_code == 200
        assert r_sel.json()["artwork"]["selected_image_id"] == img_id
        # Delete
        r_del = admin_session.delete(f"{API}/episodes/{ep_id}/artwork/{img_id}")
        assert r_del.status_code == 200
        assert not (folder / f"{img_id}.png").exists()
        # Now 404
        r_after = admin_session.get(f"{API}/episodes/{ep_id}/artwork/{img_id}.png")
        assert r_after.status_code == 404


# ---------- Regression: library list doesn't include assets/artwork.messages ----------
class TestLibraryLightweight:
    def test_library_excludes_heavy_fields(self, admin_session, episode):
        # Add artwork messages + assets to ep
        admin_session.put(f"{API}/episodes/{episode['id']}/assets",
                          json={"show_notes": "x" * 50, "description": "d", "social_posts": "p"})
        r = admin_session.get(f"{API}/episodes")
        assert r.status_code == 200
        items = r.json()
        target = next((e for e in items if e["id"] == episode["id"]), None)
        assert target is not None
        # Library list should NOT include full assets or artwork.messages
        assert "assets" not in target or not target.get("assets")
        if "artwork" in target and target["artwork"]:
            assert "messages" not in target["artwork"] or target["artwork"].get("messages") in (None, [])
