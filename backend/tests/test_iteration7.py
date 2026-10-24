"""Iteration 7 - Series pages & cover art studio."""
import io
import os
import struct
import zlib
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
ADMIN = {"username": os.environ.get("ADMIN_USERNAME", "admin"), "password": os.environ["ADMIN_PASSWORD"]}
PSALMS_ID = "a3aab385-a728-4514-a397-6dc4e6cabf25"
EP_PSALM = "e625d168-4a75-43cd-98f9-d1df18ff7191"  # 'Our Refuge and Strength' - has feed artwork
MEDIA = Path("/app/backend/media")


def _png_bytes(w=4, h=4):
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\xff\x00\x00" * w for _ in range(h))
    idat = zlib.compress(raw)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json=ADMIN)
    assert r.status_code == 200, r.text
    return s


# ---------- Series list projection ----------
def test_series_list_excludes_artwork_messages_and_concepts(sess):
    r = sess.get(f"{BASE}/series")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 3
    for s in data:
        aw = s.get("artwork") or {}
        assert "messages" not in aw, f"series {s['name']} leaks artwork.messages"
        assert "concepts" not in aw, f"series {s['name']} leaks artwork.concepts"
        assert "count" in s and isinstance(s["count"], int)


# ---------- Detail on real Psalms series (read-only) ----------
def test_psalms_detail(sess):
    r = sess.get(f"{BASE}/series/{PSALMS_ID}/detail")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["name"] == "The Most Popular Psalms"
    assert len(d["entries"]) == 2
    titles = {e["title"] for e in d["entries"]}
    assert "Our Refuge and Strength" in titles
    assert "A Soul That Thirsts for God" in titles
    books = {b["name"] for b in d["books"]}
    assert "Psalms" in books
    assert all(b["testament"] in ("OT", "NT") for b in d["books"])


# ---------- Brainstorm 400 path (openai with no key) ----------
def test_brainstorm_openai_no_key(sess):
    r = sess.post(f"{BASE}/series/{PSALMS_ID}/artwork/brainstorm",
                  json={"provider": "openai", "notes": "ignore"})
    assert r.status_code == 400
    assert "api key" in r.text.lower() or "no api key" in r.text.lower() or "brainstorm failed" in r.text.lower()


# ---------- End-to-end on a TEST series ----------
@pytest.fixture
def test_series(sess):
    r = sess.post(f"{BASE}/series", json={"name": "TEST_i7_cover", "description": "x", "color": "#123456"})
    assert r.status_code == 200, r.text
    sid = r.json()["id"]
    yield sid
    # Cleanup is covered by the destructive test; if that didn't run, nuke it here.
    sess.delete(f"{BASE}/series/{sid}")


def test_full_cover_art_flow(sess, test_series):
    sid = test_series

    # Attach the imported episode (has feed artwork). conftest restores plan_items after the suite.
    r = sess.post(f"{BASE}/series/{sid}/episodes", json={"episode_ids": [EP_PSALM]})
    assert r.status_code == 200
    assert r.json()["added"] == 1

    # Detail should list the moved episode and expose its artwork image for the picker
    d = sess.get(f"{BASE}/series/{sid}/detail").json()
    assert any(e.get("episode", {}).get("id") == EP_PSALM for e in d["entries"])
    ep_entry = next(e for e in d["entries"] if e["episode"]["id"] == EP_PSALM)
    imgs = ep_entry["episode"]["artwork"]["images"]
    assert imgs, "expected feed artwork on imported episode"
    src_img_id = imgs[0]["id"]

    # Use episode artwork
    r = sess.post(f"{BASE}/series/{sid}/artwork/from-episode",
                  json={"episode_id": EP_PSALM, "image_id": src_img_id})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["artwork"]["selected_image_id"] is not None
    assert any(i["provider"] == "episode" for i in d["artwork"]["images"])

    # Upload a valid PNG
    png = _png_bytes()
    r = sess.post(f"{BASE}/series/{sid}/artwork/upload",
                  files={"file": ("x.png", io.BytesIO(png), "image/png")})
    assert r.status_code == 200
    d = r.json()
    assert len(d["artwork"]["images"]) >= 2
    uploaded = next(i for i in d["artwork"]["images"] if i["provider"] == "upload")

    # Non-image upload -> 400
    r = sess.post(f"{BASE}/series/{sid}/artwork/upload",
                  files={"file": ("x.txt", io.BytesIO(b"hello"), "text/plain")})
    assert r.status_code == 400

    # Image endpoint 401 without cookie
    url = f"{BASE}/series/{sid}/artwork/{uploaded['id']}.png"
    r = requests.get(url)
    assert r.status_code == 401, f"expected 401, got {r.status_code}"

    # With auth, serves image/png content
    r = sess.get(url)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/")
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"

    # Select the uploaded image as cover
    r = sess.post(f"{BASE}/series/{sid}/artwork/{uploaded['id']}/select")
    assert r.status_code == 200
    assert r.json()["artwork"]["selected_image_id"] == uploaded["id"]

    # Delete the uploaded image
    r = sess.delete(f"{BASE}/series/{sid}/artwork/{uploaded['id']}")
    assert r.status_code == 200
    d = r.json()
    assert not any(i["id"] == uploaded["id"] for i in d["artwork"]["images"])
    assert not (MEDIA / "series" / sid / f"{uploaded['id']}.png").exists()

    # Delete the series -> media folder gone
    folder = MEDIA / "series" / sid
    assert folder.exists()
    r = sess.delete(f"{BASE}/series/{sid}")
    assert r.status_code == 200
    assert not folder.exists(), "series media folder should be removed on delete"

    # Series is gone
    r = sess.get(f"{BASE}/series/{sid}/detail")
    assert r.status_code == 404
