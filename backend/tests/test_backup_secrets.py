import asyncio
import io
import json
import zipfile

import pytest
from fastapi import HTTPException

import secrets_box
import setup


@pytest.fixture(autouse=True)
def secret(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "x" * 40)


def test_encrypt_roundtrip_and_legacy_plaintext():
    enc = secrets_box.encrypt("sk-test")
    assert enc.startswith("enc1:") and "sk-test" not in enc
    assert secrets_box.decrypt(enc) == "sk-test"
    assert secrets_box.decrypt("plain-old-key") == "plain-old-key"
    assert secrets_box.encrypt(enc) == enc and secrets_box.encrypt("") == ""


def test_wrong_secret_reads_as_unset(monkeypatch):
    enc = secrets_box.encrypt("sk-test")
    monkeypatch.setenv("JWT_SECRET", "y" * 40)
    assert secrets_box.decrypt(enc) == ""


def user(**kw):
    return {"id": "1", "username": "a", "password_hash": "h", "role": "admin", **kw}


def base(**kw):
    d = {c: [] for c in setup.COLLECTIONS}
    d["users"] = [user()]
    d.update(kw)
    return d


def test_validate_accepts_good_backup():
    setup._validate(base())


@pytest.mark.parametrize("data", [
    base(users=[]),
    base(users=[user(role="root")]),
    base(users=[user(role="producer")]),
    base(users=[user(), user(id="2")]),            # duplicate username
    base(users=[user(password_hash="")]),
    base(users=[user(), {"id": "2", "username": "b", "password_hash": "h", "role": "producer", "$set": 1}]),
    base(episodes=["not a dict"]),
    base(episodes=[{"a.b": 1}]),
    base(users=[user(active=False)]),
])
def test_validate_rejects_bad_backups(data):
    with pytest.raises(HTTPException) as e:
        setup._validate(data)
    assert e.value.status_code == 400


def test_backup_zip_has_no_api_keys(tmp_path, monkeypatch):
    monkeypatch.setattr(setup, "MEDIA_DIR", tmp_path / "media")
    (tmp_path / "media" / ".tmp").mkdir(parents=True)
    (tmp_path / "media" / ".tmp" / "scratch.zip").write_bytes(b"x")
    (tmp_path / "media" / "a.png").write_bytes(b"x")
    data = base(settings=[{"id": "app", "gemini_api_key": "enc1:abc", "openai_api_key": "sk", "show_name": "S"}])
    out = tmp_path / "b.zip"
    setup._write_zip(str(out), data)
    with zipfile.ZipFile(out) as z:
        blob = z.read("db/settings.json").decode()
        assert "api_key" not in blob and "show_name" in json.loads(blob)[0]
        names = z.namelist()
    assert "media/a.png" in names and not any(".tmp" in n for n in names)


def test_restore_rejects_oversize_upload(monkeypatch):
    monkeypatch.setenv("RESTORE_MAX_MB", "1")

    class Up:
        def __init__(self): self.data = io.BytesIO(b"0" * (2 * 1024 * 1024))
        async def read(self, n): return self.data.read(n)

    with pytest.raises(HTTPException) as e:
        asyncio.run(setup.restore_zip(Up()))
    assert e.value.status_code == 413
