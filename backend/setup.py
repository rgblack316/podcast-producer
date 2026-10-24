import hmac
import json
import os
import tempfile
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from audit import audit
from auth import require_admin, set_auth_cookies, user_doc
from core import db, now_iso
from media import MEDIA_DIR
from secrets_box import KEY_FIELDS, encrypt

router = APIRouter(tags=["setup"])
COLLECTIONS = ["users", "episodes", "documents", "settings", "series", "plan_items", "rss_items", "coverage_suggestions"]
APP_ID = "bible-bytes-producer"
SETUP_MAX_FAILS = 10          # wrong tokens allowed per window, per source address and overall
SETUP_LOCKOUT_MINUTES = 15


async def needs_setup() -> bool:
    return await db.users.count_documents({}) == 0


async def _check_token(token: str, request: Request):
    """Setup needs the server's SETUP_TOKEN. With no token configured setup is disabled, never open."""
    expected = os.environ.get("SETUP_TOKEN", "")
    if not expected:
        raise HTTPException(status_code=503, detail="Setup is locked: add SETUP_TOKEN to the server's .env file and restart.")
    # Per-address and overall counters (the overall one still holds if an address were ever spoofed).
    ids = [f"setup:{request.client.host if request.client else 'unknown'}", "setup:all"]
    now = datetime.now(timezone.utc)
    for ident in ids:
        row = await db.login_attempts.find_one({"identifier": ident}, {"_id": 0})
        if row and row.get("locked_until") and row["locked_until"] > now.isoformat():
            raise HTTPException(status_code=429, detail="Too many wrong setup tokens. Try again in 15 minutes.")
    if hmac.compare_digest(token.encode(), expected.encode()):
        return
    for ident in ids:
        row = await db.login_attempts.find_one({"identifier": ident}, {"_id": 0})
        count = (row or {}).get("count", 0) + 1
        update = {"identifier": ident, "count": count, "updated_at": now_iso(), "at": now}
        if count >= SETUP_MAX_FAILS:
            update["locked_until"] = (now + timedelta(minutes=SETUP_LOCKOUT_MINUTES)).isoformat()
            update["count"] = 0
        await db.login_attempts.update_one({"identifier": ident}, {"$set": update}, upsert=True)
    raise HTTPException(status_code=403, detail="Invalid setup token")


@router.get("/setup/status")
async def setup_status():
    return {"needs_setup": await needs_setup(), "token_required": True,
            "setup_disabled": not os.environ.get("SETUP_TOKEN")}


class AdminIn(BaseModel):
    username: str = Field(min_length=3)
    name: str = ""
    password: str = Field(min_length=8)


class PodcastIn(BaseModel):
    show_name: str = Field(min_length=1)
    show_tagline: str = ""
    host_names: str = ""
    show_description: str = ""
    audience: str = ""


class AiIn(BaseModel):
    default_provider: str = Field(default="gemini", pattern="^(gemini|openai)$")
    gemini_api_key: str = ""
    openai_api_key: str = ""


class SetupIn(BaseModel):
    setup_token: str = ""
    admin: AdminIn
    podcast: PodcastIn
    ai: AiIn = AiIn()


@router.post("/setup")
async def run_setup(body: SetupIn, request: Request, response: Response):
    await _check_token(body.setup_token, request)
    if not await needs_setup():
        raise HTTPException(status_code=409, detail="Setup has already been completed")
    admin = user_doc(body.admin.username, body.admin.name or body.admin.username, body.admin.password, "admin")
    await db.users.insert_one(admin)
    settings = {**body.podcast.model_dump(), "default_provider": body.ai.default_provider,
                "image_provider": body.ai.default_provider, "setup_completed_at": now_iso()}
    for k in ("gemini_api_key", "openai_api_key"):
        if getattr(body.ai, k).strip():
            settings[k] = encrypt(getattr(body.ai, k).strip())
    await db.settings.update_one({"id": "app"}, {"$set": settings}, upsert=True)
    set_auth_cookies(response, admin, request)
    await audit(request, "setup_completed", actor=admin)
    return {k: v for k, v in admin.items() if k not in ("_id", "password_hash", "mfa_secret")}


# ---------- Backup / restore ----------
def _mb(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default)) * 1024 * 1024
    except ValueError:
        return default * 1024 * 1024


MAX_DB_JSON = 256 * 1024 * 1024
MAX_FILES = 50000
ROLES = ("admin", "producer")


def _media_files():
    """Files in the media folder, skipping the scratch folder used for temporary uploads and backups."""
    scratch = MEDIA_DIR / ".tmp"
    if not MEDIA_DIR.exists():
        return
    for f in MEDIA_DIR.rglob("*"):
        if f.is_file() and scratch not in f.parents:
            yield f


def _write_zip(path: str, data: dict):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps({"app": APP_ID, "version": 2, "created_at": now_iso(),
                                                "counts": {k: len(v) for k, v in data.items()}}))
        for name, docs in data.items():
            if name == "settings":  # AI provider keys are never put in a backup; re-enter them after a fresh restore
                docs = [{k: v for k, v in d.items() if k not in KEY_FIELDS} for d in docs]
            z.writestr(f"db/{name}.json", json.dumps(docs, default=str))
        for f in _media_files():
            z.write(f, f"media/{f.relative_to(MEDIA_DIR).as_posix()}")


@router.get("/backup")
async def download_backup(request: Request, admin: dict = Depends(require_admin)):
    await audit(request, "backup_download", actor=admin)
    data = {c: await db[c].find({}, {"_id": 0}).to_list(None) for c in COLLECTIONS}
    fd, path = tempfile.mkstemp(suffix=".zip")
    os.close(fd)
    _write_zip(path, data)
    stamp = now_iso()[:10]
    return FileResponse(path, media_type="application/zip", filename=f"bible-bytes-backup-{stamp}.zip",
                        headers={"Cache-Control": "no-store"}, background=BackgroundTask(os.remove, path))


def _bad(msg: str):
    raise HTTPException(status_code=400, detail=msg)


def _validate(data: dict):
    for c, docs in data.items():
        if not isinstance(docs, list) or not all(isinstance(d, dict) for d in docs):
            _bad(f"Backup data for '{c}' is malformed")
        if any(k.startswith("$") or "." in k for d in docs for k in d):
            _bad(f"Backup data for '{c}' contains invalid field names")
    names, ids = set(), set()
    for u in data["users"]:
        if not all(isinstance(u.get(k), str) and u[k] for k in ("id", "username", "password_hash")) or u.get("role") not in ROLES:
            _bad("Backup contains a malformed user account")
        if u["username"] in names or u["id"] in ids:
            _bad("Backup contains duplicate user accounts")
        names.add(u["username"])
        ids.add(u["id"])
    if not any(u["role"] == "admin" and u.get("active", True) for u in data["users"]):
        _bad("Backup contains no active admin account")


async def _spool_upload(file: UploadFile) -> str:
    """Copy the upload to disk with a size limit; returns the temp file path."""
    limit = _mb("RESTORE_MAX_MB", 2048)
    fd, path = tempfile.mkstemp(suffix=".zip")
    size = 0
    try:
        with os.fdopen(fd, "wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(status_code=413, detail=f"Backup file is larger than the {limit // 1048576} MB limit")
                out.write(chunk)
    except BaseException:
        os.remove(path)
        raise
    return path


async def restore_zip(file: UploadFile) -> dict:
    path = await _spool_upload(file)
    try:
        return await _restore_from(path)
    finally:
        os.remove(path)


async def _restore_from(path: str) -> dict:
    try:
        z = zipfile.ZipFile(path)
        infos = {i.filename: i for i in z.infolist()}
        if "manifest.json" not in infos or infos["manifest.json"].file_size > 1024 * 1024:
            raise KeyError
        manifest = json.loads(z.read("manifest.json"))
    except (zipfile.BadZipFile, KeyError, ValueError):
        _bad("This is not a valid Bible Bytes backup file")
    if manifest.get("app") != APP_ID:
        _bad("This backup was not created by Bible Bytes Producer")
    if len(infos) > MAX_FILES or sum(i.file_size for i in infos.values()) > _mb("RESTORE_MAX_UNCOMPRESSED_MB", 4096):
        raise HTTPException(status_code=413, detail="Backup is too large to restore")
    data = {}
    for c in COLLECTIONS:
        info = infos.get(f"db/{c}.json")
        if info is None:
            data[c] = []
            continue
        if info.file_size > MAX_DB_JSON:
            _bad(f"Backup data for '{c}' is too large")
        try:
            data[c] = json.loads(z.read(info))
        except ValueError:
            _bad(f"Backup data for '{c}' is not valid")
    _validate(data)  # everything is checked before anything is deleted

    # AI keys: keep the ones already on this server; accept (and encrypt) keys from older backups
    current = await db.settings.find_one({"id": "app"}, {"_id": 0}) or {}
    for d in data["settings"]:
        for k in KEY_FIELDS:
            v = d.get(k)
            if isinstance(v, str) and v:
                d[k] = encrypt(v)
            elif current.get(k):
                d[k] = current[k]
            else:
                d.pop(k, None)

    for c, docs in data.items():
        await db[c].delete_many({})
        if docs:
            await db[c].insert_many(docs)
    await db.login_attempts.delete_many({})
    await db.rss_jobs.delete_many({})
    root = MEDIA_DIR.resolve()
    for f in list(_media_files()):
        f.unlink()
    for name, info in infos.items():
        if not name.startswith("media/") or name.endswith("/"):
            continue
        target = (MEDIA_DIR / name[len("media/"):]).resolve()
        if root not in target.parents or (root / ".tmp") in target.parents:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with z.open(info) as src, open(target, "wb") as dst:
            left = info.file_size  # never write more than the archive declared
            while left > 0 and (chunk := src.read(min(1024 * 1024, left))):
                dst.write(chunk)
                left -= len(chunk)
    return {"restored": {c: len(d) for c, d in data.items()}, "backup_created_at": manifest.get("created_at")}


@router.post("/setup/restore")
async def setup_restore(request: Request, file: UploadFile = File(...), setup_token: str = Form("")):
    await _check_token(setup_token, request)
    if not await needs_setup():
        raise HTTPException(status_code=409, detail="Setup has already been completed")
    result = await restore_zip(file)
    await audit(request, "setup_restore")
    return result


@router.post("/backup/restore")
async def admin_restore(request: Request, response: Response, file: UploadFile = File(...),
                        admin: dict = Depends(require_admin)):
    result = await restore_zip(file)
    await audit(request, "backup_restored", actor=admin)
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return result


Path(MEDIA_DIR).mkdir(parents=True, exist_ok=True)
