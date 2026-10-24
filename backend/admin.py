import json
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

import llm
from audit import audit
from secrets_box import KEY_FIELDS, encrypt
import prompts
from auth import get_current_user, require_admin
from core import db, now_iso, new_id, NO_ID
from docx_utils import extract_text
from episodes import new_episode

settings_router = APIRouter(prefix="/settings", tags=["settings"])
docs_router = APIRouter(prefix="/documents", tags=["documents"])
MAX_UPLOAD = 15 * 1024 * 1024


def _mask(key: str) -> str:
    return f"••••••••{key[-4:]}" if key else ""


def _public(s: dict) -> dict:
    return {"show_name": s["show_name"], "default_provider": s["default_provider"],
            "gemini_model": s["gemini_model"], "openai_model": s["openai_model"],
            "image_provider": s["image_provider"], "gemini_image_model": s["gemini_image_model"],
            "openai_image_model": s["openai_image_model"],
            "show_tagline": s["show_tagline"], "host_names": s["host_names"],
            "show_description": s["show_description"], "audience": s["audience"],
            "gemini_configured": bool(s["gemini_api_key"]), "openai_configured": bool(s["openai_api_key"])}


class SettingsIn(BaseModel):
    show_name: Optional[str] = None
    default_provider: Optional[str] = None
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = None
    openai_api_key: Optional[str] = None
    openai_model: Optional[str] = None
    extra_instructions: Optional[str] = None
    image_provider: Optional[str] = None
    gemini_image_model: Optional[str] = None
    openai_image_model: Optional[str] = None
    show_tagline: Optional[str] = None
    host_names: Optional[str] = None
    show_description: Optional[str] = None
    audience: Optional[str] = None


@settings_router.get("/public")
async def public_settings(_: dict = Depends(get_current_user)):
    return _public(await llm.get_settings())


@settings_router.get("/audit")
async def audit_log(limit: int = 100, skip: int = 0, action: str = "", _: dict = Depends(require_admin)):
    q = {"action": action} if action else {}
    rows = await db.audit_log.find(q, {"_id": 0}).sort("at", -1).skip(max(0, skip)).limit(min(max(1, limit), 500)).to_list(500)
    for r in rows:
        r["at"] = r["at"].isoformat()
    return rows


@settings_router.get("")
async def get_settings(_: dict = Depends(require_admin)):
    s = await llm.get_settings()
    return {**_public(s), "extra_instructions": s["extra_instructions"],
            "gemini_api_key_masked": _mask(s["gemini_api_key"]), "openai_api_key_masked": _mask(s["openai_api_key"])}


@settings_router.put("")
async def update_settings(body: SettingsIn, request: Request, admin: dict = Depends(require_admin)):
    changes = {k: v.strip() if isinstance(v, str) and k != "extra_instructions" else v
               for k, v in body.model_dump(exclude_none=True).items()}
    for k in ("gemini_api_key", "openai_api_key"):
        if k in changes and not changes[k]:
            changes.pop(k)
    if "default_provider" in changes and changes["default_provider"] not in ("gemini", "openai"):
        raise HTTPException(status_code=400, detail="Provider must be gemini or openai")
    if "image_provider" in changes and changes["image_provider"] not in ("gemini", "openai"):
        raise HTTPException(status_code=400, detail="Image provider must be gemini or openai")
    for k in KEY_FIELDS:
        if k in changes:
            changes[k] = encrypt(changes[k])
    changes.update({"updated_at": now_iso(), "updated_by": admin["username"]})
    await db.settings.update_one({"id": "app"}, {"$set": changes}, upsert=True)
    await audit(request, "settings_updated", actor=admin, fields=sorted(k for k in changes if k not in ("updated_at", "updated_by")))
    return await get_settings(admin)


class TestIn(BaseModel):
    provider: str


@settings_router.post("/test")
async def test_provider(body: TestIn, _: dict = Depends(require_admin)):
    s = await llm.get_settings()
    provider = llm.resolve_provider(s, body.provider)
    try:
        reply = await llm.generate(s, provider, "You are a helpful assistant.", "Reply with exactly: Connection OK")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)[:500])
    return {"ok": True, "reply": reply[:200], "model": s[f"{provider}_model"]}


# ---------- Reference documents ----------
def _doc_summary(d: dict) -> dict:
    return {**{k: v for k, v in d.items() if k != "text"}, "char_count": len(d["text"]), "preview": d["text"][:400]}


@docs_router.get("")
async def list_documents(_: dict = Depends(get_current_user)):
    docs = await db.documents.find({}, NO_ID).sort("created_at", -1).to_list(500)
    return [_doc_summary(d) for d in docs]


@docs_router.get("/{doc_id}")
async def get_document(doc_id: str, _: dict = Depends(get_current_user)):
    d = await db.documents.find_one({"id": doc_id}, NO_ID)
    if not d:
        raise HTTPException(status_code=404, detail="Document not found")
    return {k: v for k, v in d.items() if k != "_id"}


@docs_router.post("/upload")
async def upload_document(file: UploadFile = File(...), kind: str = Form(...), admin: dict = Depends(require_admin)):
    if kind not in ("template", "example"):
        raise HTTPException(status_code=400, detail="kind must be template or example")
    if not (file.filename or "").lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are supported")
    data = await file.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(status_code=400, detail="File is larger than 15 MB")
    try:
        text = extract_text(data)
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read this .docx file")
    if not text.strip():
        raise HTTPException(status_code=400, detail="No text found in this document")
    if kind == "template":
        await db.documents.update_many({"kind": "template"}, {"$set": {"active": False}})
    doc = {"id": new_id(), "kind": kind, "filename": file.filename, "text": text, "active": True,
           "imported_episode_id": None, "uploaded_by": admin["username"], "created_at": now_iso()}
    await db.documents.insert_one(doc)
    return _doc_summary({k: v for k, v in doc.items() if k != "_id"})


class DocPatch(BaseModel):
    active: bool


@docs_router.patch("/{doc_id}")
async def patch_document(doc_id: str, body: DocPatch, _: dict = Depends(require_admin)):
    d = await db.documents.find_one({"id": doc_id}, NO_ID)
    if not d:
        raise HTTPException(status_code=404, detail="Document not found")
    if d["kind"] == "template" and body.active:
        await db.documents.update_many({"kind": "template"}, {"$set": {"active": False}})
    await db.documents.update_one({"id": doc_id}, {"$set": {"active": body.active}})
    return _doc_summary(await db.documents.find_one({"id": doc_id}, NO_ID))


@docs_router.delete("/{doc_id}")
async def delete_document(doc_id: str, _: dict = Depends(require_admin)):
    res = await db.documents.delete_one({"id": doc_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"ok": True}


class SuggestIn(BaseModel):
    provider: Optional[str] = None


@docs_router.post("/{doc_id}/suggest-metadata")
async def suggest_metadata(doc_id: str, body: SuggestIn, _: dict = Depends(require_admin)):
    d = await get_document(doc_id, _)
    s = await llm.get_settings()
    provider = llm.resolve_provider(s, body.provider)
    try:
        raw = await llm.generate(s, provider, "You extract structured metadata and reply with JSON only.",
                                 prompts.metadata_prompt(d["text"]))
        match = re.search(r"\{.*\}", raw, re.S)
        data = json.loads(match.group(0) if match else raw)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"AI suggestion failed: {str(e)[:300]}")
    return {"title": str(data.get("title", "")), "episode_number": str(data.get("episode_number", "") or ""),
            "topic": str(data.get("topic", "")), "primary_scripture": str(data.get("primary_scripture", "")),
            "supporting_scriptures": [str(x) for x in data.get("supporting_scriptures") or []],
            "themes": [str(x) for x in data.get("themes") or []]}


class ImportIn(BaseModel):
    title: str
    episode_number: str = ""
    topic: str
    primary_scripture: str
    supporting_scriptures: List[str] = []
    themes: List[str] = []


@docs_router.post("/{doc_id}/import")
async def import_document(doc_id: str, body: ImportIn, admin: dict = Depends(require_admin)):
    d = await get_document(doc_id, admin)
    if d["kind"] != "example":
        raise HTTPException(status_code=400, detail="Only example episodes can be imported")
    if d.get("imported_episode_id"):
        raise HTTPException(status_code=400, detail="This document was already imported")
    ep = new_episode(body.model_dump(), admin, status="published")
    ep.update({"script": d["text"], "imported": True, "source_document_id": doc_id, "published_at": now_iso()})
    await db.episodes.insert_one(ep)
    await db.documents.update_one({"id": doc_id}, {"$set": {"imported_episode_id": ep["id"]}})
    return {"episode_id": ep["id"]}
