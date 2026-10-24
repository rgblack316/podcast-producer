import io
import json
import os
import tempfile
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from auth import require_admin, set_auth_cookies, user_doc
from core import db, now_iso
from media import MEDIA_DIR

router = APIRouter(tags=["setup"])
COLLECTIONS = ["users", "episodes", "documents", "settings", "series", "plan_items", "rss_items", "coverage_suggestions"]
APP_ID = "bible-bytes-producer"


async def needs_setup() -> bool:
    return await db.users.count_documents({}) == 0


def _check_token(token: str):
    expected = os.environ.get("SETUP_TOKEN", "")
    if expected and token != expected:
        raise HTTPException(status_code=403, detail="Invalid setup token")


@router.get("/setup/status")
async def setup_status():
    return {"needs_setup": await needs_setup(), "token_required": bool(os.environ.get("SETUP_TOKEN"))}


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
async def run_setup(body: SetupIn, response: Response):
    _check_token(body.setup_token)
    if not await needs_setup():
        raise HTTPException(status_code=409, detail="Setup has already been completed")
    admin = user_doc(body.admin.username, body.admin.name or body.admin.username, body.admin.password, "admin")
    await db.users.insert_one(admin)
    settings = {**body.podcast.model_dump(), "default_provider": body.ai.default_provider,
                "image_provider": body.ai.default_provider, "setup_completed_at": now_iso()}
    for k in ("gemini_api_key", "openai_api_key"):
        if getattr(body.ai, k).strip():
            settings[k] = getattr(body.ai, k).strip()
    await db.settings.update_one({"id": "app"}, {"$set": settings}, upsert=True)
    set_auth_cookies(response, admin["id"])
    return {k: v for k, v in admin.items() if k not in ("_id", "password_hash", "mfa_secret")}


# ---------- Backup / restore ----------
def _write_zip(path: str, data: dict):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps({"app": APP_ID, "version": 1, "created_at": now_iso(),
                                                "counts": {k: len(v) for k, v in data.items()}}))
        for name, docs in data.items():
            z.writestr(f"db/{name}.json", json.dumps(docs, default=str))
        if MEDIA_DIR.exists():
            for f in MEDIA_DIR.rglob("*"):
                if f.is_file():
                    z.write(f, f"media/{f.relative_to(MEDIA_DIR).as_posix()}")


@router.get("/backup")
async def download_backup(_: dict = Depends(require_admin)):
    data = {c: await db[c].find({}, {"_id": 0}).to_list(None) for c in COLLECTIONS}
    fd, path = tempfile.mkstemp(suffix=".zip")
    os.close(fd)
    _write_zip(path, data)
    stamp = now_iso()[:10]
    return FileResponse(path, media_type="application/zip", filename=f"bible-bytes-backup-{stamp}.zip",
                        background=BackgroundTask(os.remove, path))


async def restore_zip(raw: bytes) -> dict:
    try:
        z = zipfile.ZipFile(io.BytesIO(raw))
        manifest = json.loads(z.read("manifest.json"))
    except (zipfile.BadZipFile, KeyError, ValueError):
        raise HTTPException(status_code=400, detail="This is not a valid Bible Bytes backup file")
    if manifest.get("app") != APP_ID:
        raise HTTPException(status_code=400, detail="This backup was not created by Bible Bytes Producer")
    data = {}
    for c in COLLECTIONS:
        try:
            data[c] = json.loads(z.read(f"db/{c}.json"))
        except KeyError:
            data[c] = []
    if not any(u.get("role") == "admin" for u in data["users"]):
        raise HTTPException(status_code=400, detail="Backup contains no admin account")
    for c, docs in data.items():
        await db[c].delete_many({})
        if docs:
            await db[c].insert_many(docs)
    await db.login_attempts.delete_many({})
    await db.rss_jobs.delete_many({})
    root = MEDIA_DIR.resolve()
    for f in list(MEDIA_DIR.rglob("*")) if MEDIA_DIR.exists() else []:
        if f.is_file():
            f.unlink()
    for name in z.namelist():
        if not name.startswith("media/") or name.endswith("/"):
            continue
        target = (MEDIA_DIR / name[len("media/"):]).resolve()
        if root not in target.parents:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(z.read(name))
    return {"restored": {c: len(d) for c, d in data.items()}, "backup_created_at": manifest.get("created_at")}


@router.post("/setup/restore")
async def setup_restore(file: UploadFile = File(...), setup_token: str = Form("")):
    _check_token(setup_token)
    if not await needs_setup():
        raise HTTPException(status_code=409, detail="Setup has already been completed")
    return await restore_zip(await file.read())


@router.post("/backup/restore")
async def admin_restore(request: Request, response: Response, file: UploadFile = File(...),
                        _: dict = Depends(require_admin)):
    result = await restore_zip(await file.read())
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return result


Path(MEDIA_DIR).mkdir(parents=True, exist_ok=True)
