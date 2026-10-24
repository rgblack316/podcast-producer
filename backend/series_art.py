import logging
import shutil
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

import llm
from auth import get_current_user
from bible import BOOKS
from core import db, now_iso, new_id, NO_ID
from media import series_dir, series_image_path, episode_image_path
from extras import OLD_TESTAMENT, _gemini_image, _openai_image, _parse_json, _sniff, _spawn

router = APIRouter(prefix="/series", tags=["series"])
log = logging.getLogger(__name__)
MAX_UPLOAD = 10 * 1024 * 1024
EP_FIELDS = {"_id": 0, "id": 1, "title": 1, "episode_number": 1, "status": 1, "topic": 1, "primary_scripture": 1,
             "themes": 1, "books": 1, "chapters": 1, "published_at": 1, "artwork.images": 1,
             "artwork.selected_image_id": 1}


def _art(s: dict) -> dict:
    return {"messages": [], "concepts": [], "images": [], "selected_image_id": None, **(s.get("artwork") or {})}


async def _get_series(series_id: str) -> dict:
    s = await db.series.find_one({"id": series_id}, NO_ID)
    if not s:
        raise HTTPException(status_code=404, detail="Series not found")
    return {k: v for k, v in s.items() if k != "_id"}


async def _detail(series_id: str) -> dict:
    s = await _get_series(series_id)
    items = await db.plan_items.find({"series_id": series_id}, NO_ID).to_list(2000)
    eps = {e["id"]: e for e in await db.episodes.find(
        {"id": {"$in": [i["episode_id"] for i in items if i.get("episode_id")]}}, EP_FIELDS).to_list(2000)}
    entries, books, themes = [], {}, {}
    for i in items:
        ep = eps.get(i.get("episode_id"))
        entries.append({"plan_id": i["id"], "date": i.get("date") or (ep or {}).get("published_at", "")[:10] or None,
                        "title": (ep or {}).get("title") or i["title"], "episode": ep,
                        "primary_scripture": (ep or {}).get("primary_scripture") or i.get("primary_scripture", ""),
                        "topic": (ep or {}).get("topic") or i.get("topic", "")})
        for b in (ep or {}).get("books") or []:
            books[b] = books.get(b, 0) + 1
        for t in (ep or {}).get("themes") or i.get("themes") or []:
            themes[t.lower()] = themes.get(t.lower(), 0) + 1
    entries.sort(key=lambda e: e["date"] or "9999")
    order = [b for b, _ in BOOKS]
    book_list = sorted(({"name": b, "count": c, "testament": "OT" if b in OLD_TESTAMENT else "NT"}
                        for b, c in books.items()), key=lambda x: order.index(x["name"]) if x["name"] in order else 99)
    return {**s, "artwork": _art(s), "entries": entries, "books": book_list,
            "themes": [{"name": k, "count": v} for k, v in sorted(themes.items(), key=lambda x: -x[1])]}


@router.get("/{series_id}/detail")
async def series_detail(series_id: str, _: dict = Depends(get_current_user)):
    return await _detail(series_id)


async def _add_image(series_id: str, data: bytes, meta: dict) -> str:
    s = await _get_series(series_id)
    art = _art(s)
    img_id = new_id()
    series_dir(series_id).mkdir(parents=True, exist_ok=True)
    series_image_path(series_id, img_id).write_bytes(data)
    img = {"id": img_id, "concept_id": None, "created_at": now_iso(), **meta}
    await db.series.update_one({"id": series_id}, {"$set": {
        "artwork": {**art, "images": art["images"] + [img], "selected_image_id": art["selected_image_id"] or img_id},
        "art_generating": None, "art_error": None}})
    return img_id


@router.post("/{series_id}/artwork/upload")
async def upload_cover(series_id: str, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    data = await file.read()
    if not (file.content_type or "").startswith("image/") or len(data) > MAX_UPLOAD:
        raise HTTPException(status_code=400, detail="Upload a PNG, JPG or WebP image up to 10 MB")
    await _add_image(series_id, data, {"prompt": f"Uploaded: {file.filename}", "provider": "upload", "created_by": user["username"]})
    return await _detail(series_id)


class FromEpisodeIn(BaseModel):
    episode_id: str
    image_id: str


@router.post("/{series_id}/artwork/from-episode")
async def cover_from_episode(series_id: str, body: FromEpisodeIn, user: dict = Depends(get_current_user)):
    src = episode_image_path(body.episode_id, body.image_id)
    if not src.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    img_id = await _add_image(series_id, src.read_bytes(), {"prompt": "Copied from an episode", "provider": "episode",
                                                           "source_episode_id": body.episode_id, "created_by": user["username"]})
    await db.series.update_one({"id": series_id}, {"$set": {"artwork.selected_image_id": img_id}})
    return await _detail(series_id)


class BrainstormIn(BaseModel):
    provider: Optional[str] = None
    notes: str = ""


@router.post("/{series_id}/artwork/brainstorm")
async def brainstorm(series_id: str, body: BrainstormIn, user: dict = Depends(get_current_user)):
    d = await _detail(series_id)
    art = d["artwork"]
    settings = await llm.get_settings()
    provider = llm.resolve_provider(settings, body.provider)
    eps = "\n".join(f"- {e['title']} ({e['primary_scripture']}): {e['topic']}" for e in d["entries"][:40]) or "(no episodes yet)"
    history = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in art["messages"][-12:])
    prompt = (f"PODCAST: {settings['show_name']}\nSERIES: {d['name']}\nDESCRIPTION: {d.get('description') or 'n/a'}\n"
              f"EPISODES IN THE SERIES:\n{eps}\n\nCONVERSATION SO FAR\n{history or '(start)'}\n\n"
              f"PRODUCER'S LATEST NOTE\n{body.notes or 'Propose initial ideas.'}\n\n"
              "You are an art director brainstorming square (1:1) cover artwork for this podcast SERIES. Respond to the "
              "note and propose 3-4 distinct visual concepts that unify the series. Reverent, legible as a thumbnail. "
              "Return ONLY JSON: {\"reply\": \"\", \"concepts\": [{\"title\": \"\", \"description\": \"\", \"prompt\": \"\"}]}")
    try:
        data = _parse_json(await llm.generate(settings, provider, "You are a creative art director. Reply with JSON only.", prompt))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Brainstorm failed: {str(e)[:300]}")
    concepts = [{"id": new_id(), "title": str(c.get("title", "")), "description": str(c.get("description", "")),
                 "prompt": str(c.get("prompt", "")), "created_at": now_iso()} for c in data.get("concepts") or [] if isinstance(c, dict)]
    msgs = ([{"role": "producer", "content": body.notes.strip(), "by": user["username"], "created_at": now_iso()}]
            if body.notes.strip() else [])
    msgs.append({"role": "assistant", "content": str(data.get("reply", "")), "created_at": now_iso()})
    await db.series.update_one({"id": series_id}, {"$set": {"artwork": {
        **art, "messages": art["messages"] + msgs, "concepts": art["concepts"] + concepts}}})
    return await _detail(series_id)


class GenIn(BaseModel):
    prompt: str
    provider: Optional[str] = None
    concept_id: Optional[str] = None


async def _run(series_id: str, provider: str, prompt: str, user: dict):
    try:
        s = await llm.get_settings()
        fn = _gemini_image if provider == "gemini" else _openai_image
        data = await fn(s[f"{provider}_api_key"], s[f"{provider}_image_model"], prompt)
        await _add_image(series_id, data, {"prompt": prompt, "provider": f"{provider}:{s[f'{provider}_image_model']}",
                                           "created_by": user["username"]})
    except Exception as e:
        log.exception("series image failed")
        await db.series.update_one({"id": series_id}, {"$set": {"art_generating": None, "art_error": str(e)[:800]}})


@router.post("/{series_id}/artwork/generate")
async def generate(series_id: str, body: GenIn, user: dict = Depends(get_current_user)):
    s = await _get_series(series_id)
    if not body.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt is empty")
    if s.get("art_generating"):
        raise HTTPException(status_code=409, detail="Artwork is already being generated")
    settings = await llm.get_settings()
    provider = llm.resolve_provider(settings, body.provider or settings["image_provider"])
    await db.series.update_one({"id": series_id}, {"$set": {"art_generating": {"provider": provider, "started_at": now_iso()},
                                                            "art_error": None}})
    _spawn(_run(series_id, provider, body.prompt.strip(), user))
    return await _detail(series_id)


@router.get("/{series_id}/artwork/{img_id}.png")
async def image_file(series_id: str, img_id: str, _: dict = Depends(get_current_user)):
    path = series_image_path(series_id, img_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path, media_type=_sniff(path), headers={"Cache-Control": "private, max-age=86400"})


@router.post("/{series_id}/artwork/{img_id}/select")
async def select(series_id: str, img_id: str, _: dict = Depends(get_current_user)):
    art = _art(await _get_series(series_id))
    if not any(i["id"] == img_id for i in art["images"]):
        raise HTTPException(status_code=404, detail="Image not found")
    await db.series.update_one({"id": series_id}, {"$set": {"artwork.selected_image_id": img_id}})
    return await _detail(series_id)


@router.delete("/{series_id}/artwork/{img_id}")
async def delete_image(series_id: str, img_id: str, _: dict = Depends(get_current_user)):
    art = _art(await _get_series(series_id))
    images = [i for i in art["images"] if i["id"] != img_id]
    if len(images) == len(art["images"]):
        raise HTTPException(status_code=404, detail="Image not found")
    series_image_path(series_id, img_id).unlink(missing_ok=True)
    sel = art["selected_image_id"] if art["selected_image_id"] != img_id else (images[-1]["id"] if images else None)
    await db.series.update_one({"id": series_id}, {"$set": {"artwork": {**art, "images": images, "selected_image_id": sel}}})
    return await _detail(series_id)


def remove_series_media(series_id: str):
    shutil.rmtree(series_dir(series_id), ignore_errors=True)

