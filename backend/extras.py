import asyncio
import base64
import json
import logging
import os
import re
from pathlib import Path
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

import llm
import prompts
from auth import get_current_user
from bible import BOOKS
from core import db, now_iso, new_id, NO_ID
from episodes import _get

router = APIRouter(tags=["extras"])
log = logging.getLogger(__name__)
_tasks = set()
MEDIA_DIR = Path(os.environ["MEDIA_DIR"])
OLD_TESTAMENT = [b for b, _ in BOOKS[:39]]


def _spawn(coro):
    t = asyncio.create_task(coro)
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)


def _parse_json(raw: str):
    m = re.search(r"[\[{].*[\]}]", raw, re.S)
    return json.loads(m.group(0) if m else raw)


# ---------- Production assets: show notes, description, social posts ----------
class AssetsGenIn(BaseModel):
    provider: Optional[str] = None
    notes: str = ""


class AssetsIn(BaseModel):
    show_notes: str = ""
    description: str = ""
    social_posts: str = ""


def assets_prompt(ep: dict, notes: str, current: dict | None) -> str:
    base = (f"EPISODE INTAKE\n{prompts.intake_block(ep)}\n\nFINAL SCRIPT\n{(ep.get('script') or '')[:60000]}\n\n")
    if current and notes:
        base += f"CURRENT ASSETS\n{json.dumps(current)}\n\nREVISION NOTES\n{notes}\n\n"
    elif notes:
        base += f"PRODUCER NOTES\n{notes}\n\n"
    return base + (
        "Create the publishing assets for this episode. Return ONLY a JSON object (no code fences) with keys:\n"
        "show_notes: Markdown show notes with a short summary, key takeaways as bullets, all scripture references "
        "mentioned, and reflection questions.\n"
        "description: a 2-4 sentence plain-text episode description for podcast apps.\n"
        "social_posts: Markdown with sections '## Instagram', '## Facebook', '## X / Twitter' and '## YouTube', each "
        "containing a ready-to-post caption with relevant hashtags.")


async def _run_assets(ep_id: str, provider: str, notes: str, user: dict):
    try:
        ep = await _get(ep_id)
        settings = await llm.get_settings()
        ctx = await prompts.reference_context()
        raw = await llm.generate(settings, provider, prompts.system_prompt(settings, ctx) +
                                 "\n\nFor this task, reply with JSON only as instructed.",
                                 assets_prompt(ep, notes, ep.get("assets")))
        data = _parse_json(raw)
        assets = {k: str(data.get(k, "")).strip() for k in ("show_notes", "description", "social_posts")}
        assets.update({"updated_at": now_iso(), "updated_by": user["username"],
                       "provider": f"{provider}:{settings[f'{provider}_model']}"})
        await db.episodes.update_one({"id": ep_id}, {"$set": {"assets": assets, "generating": None, "last_error": None}})
    except Exception as e:
        log.exception("assets generation failed")
        await db.episodes.update_one({"id": ep_id}, {"$set": {"generating": None, "last_error": str(e)[:800]}})


@router.post("/episodes/{ep_id}/assets/generate")
async def generate_assets(ep_id: str, body: AssetsGenIn, user: dict = Depends(get_current_user)):
    ep = await _get(ep_id)
    if ep["status"] not in ("script_complete", "published"):
        raise HTTPException(status_code=400, detail="Mark the script complete before creating show notes")
    if ep.get("generating"):
        raise HTTPException(status_code=409, detail="A generation is already running for this episode")
    settings = await llm.get_settings()
    provider = llm.resolve_provider(settings, body.provider)
    await db.episodes.update_one({"id": ep_id}, {"$set": {
        "generating": {"stage": "assets", "provider": provider, "started_at": now_iso(), "by": user["username"]},
        "last_error": None}})
    _spawn(_run_assets(ep_id, provider, body.notes.strip(), user))
    return await _get(ep_id)


@router.put("/episodes/{ep_id}/assets")
async def save_assets(ep_id: str, body: AssetsIn, user: dict = Depends(get_current_user)):
    ep = await _get(ep_id)
    assets = {**(ep.get("assets") or {}), **body.model_dump(), "source": "manual", "updated_at": now_iso(),
              "updated_by": user["username"]}
    await db.episodes.update_one({"id": ep_id}, {"$set": {"assets": assets}})
    return await _get(ep_id)


# ---------- Coverage map ----------
@router.get("/coverage")
async def coverage(_: dict = Depends(get_current_user)):
    eps = await db.episodes.find({}, {"_id": 0, "id": 1, "title": 1, "episode_number": 1, "books": 1, "themes": 1,
                                      "status": 1, "created_at": 1, "published_at": 1}).to_list(5000)
    books = {b: [] for b, _ in BOOKS}
    themes, months = {}, {}
    for e in eps:
        ref = {"id": e["id"], "title": e["title"], "episode_number": e.get("episode_number"), "status": e["status"]}
        for b in e.get("books") or []:
            books.setdefault(b, []).append(ref)
        month = (e.get("published_at") or e["created_at"])[:7]
        months.setdefault(month, {"month": month, "count": 0, "themes": {}})
        months[month]["count"] += 1
        for t in e.get("themes") or []:
            key = t.lower()
            themes.setdefault(key, {"name": key, "count": 0, "first": month, "last": month})
            themes[key]["count"] += 1
            themes[key]["first"] = min(themes[key]["first"], month)
            themes[key]["last"] = max(themes[key]["last"], month)
            months[month]["themes"][key] = months[month]["themes"].get(key, 0) + 1
    book_list = [{"name": b, "testament": "OT" if b in OLD_TESTAMENT else "NT", "count": len(books[b]),
                  "episodes": books[b]} for b, _ in BOOKS]
    saved = await db.coverage_suggestions.find_one({"id": "latest"}, NO_ID)
    return {"total": len(eps), "books": book_list, "themes": sorted(themes.values(), key=lambda t: -t["count"]),
            "timeline": [{**m, "themes": m["themes"]} for _, m in sorted(months.items())],
            "suggestions": (saved or {}).get("items", []), "suggested_at": (saved or {}).get("created_at")}


class SuggestIn(BaseModel):
    provider: Optional[str] = None
    focus: str = ""
    count: int = 6


@router.post("/coverage/suggest")
async def suggest_topics(body: SuggestIn, user: dict = Depends(get_current_user)):
    settings = await llm.get_settings()
    provider = llm.resolve_provider(settings, body.provider)
    cov = await coverage(user)
    covered_books = [f"{b['name']} ({b['count']})" for b in cov["books"] if b["count"]]
    uncovered = [b["name"] for b in cov["books"] if not b["count"]]
    themes = [f"{t['name']} ({t['count']})" for t in cov["themes"]]
    prompt = (f"Past episodes:\n{await prompts.covered_summary(None)}\n\nBooks covered (episode count): "
              f"{', '.join(covered_books) or 'none'}\nBooks never covered: {', '.join(uncovered)}\n"
              f"Themes covered (count): {', '.join(themes) or 'none'}\n"
              f"{'Producer focus: ' + body.focus if body.focus.strip() else ''}\n\n"
              f"Suggest {max(1, min(body.count, 12))} future episodes that fill gaps in books and themes while staying "
              "true to the show. Return ONLY a JSON array (no code fences) of objects with keys: title, topic, "
              "primary_scripture, supporting_scriptures (array), themes (array of 2-4), why (one sentence about the gap it fills).")
    try:
        raw = await llm.generate(settings, provider, prompts.system_prompt(settings, {"template": "", "examples": []})
                                 + "\n\nFor this task, reply with JSON only.", prompt)
        items = _parse_json(raw)
        if isinstance(items, dict):
            items = next((v for v in items.values() if isinstance(v, list)), [])
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"AI suggestion failed: {str(e)[:300]}")
    clean = [{"id": new_id(), "title": str(i.get("title", "")), "topic": str(i.get("topic", "")),
              "primary_scripture": str(i.get("primary_scripture", "")),
              "supporting_scriptures": [str(x) for x in i.get("supporting_scriptures") or []],
              "themes": [str(x) for x in i.get("themes") or []], "why": str(i.get("why", ""))}
             for i in items if isinstance(i, dict)]
    await db.coverage_suggestions.update_one({"id": "latest"}, {"$set": {
        "items": clean, "created_at": now_iso(), "by": user["username"]}}, upsert=True)
    return {"suggestions": clean}


# ---------- Artwork studio ----------
class BrainstormIn(BaseModel):
    provider: Optional[str] = None
    notes: str = ""


class ArtGenIn(BaseModel):
    prompt: str
    provider: Optional[str] = None
    concept_id: Optional[str] = None


def _artwork(ep: dict) -> dict:
    return {"messages": [], "concepts": [], "images": [], "selected_image_id": None, **(ep.get("artwork") or {})}


@router.post("/episodes/{ep_id}/artwork/brainstorm")
async def brainstorm(ep_id: str, body: BrainstormIn, user: dict = Depends(get_current_user)):
    ep = await _get(ep_id)
    art = _artwork(ep)
    settings = await llm.get_settings()
    provider = llm.resolve_provider(settings, body.provider)
    history = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in art["messages"][-12:])
    prev = json.dumps([{k: c[k] for k in ("title", "description")} for c in art["concepts"][-8:]])
    prompt = (f"EPISODE\n{prompts.intake_block(ep)}\n\nOUTLINE EXCERPT\n{(ep.get('outline') or '')[:4000]}\n\n"
              f"PREVIOUS CONCEPTS\n{prev}\n\nCONVERSATION SO FAR\n{history or '(start)'}\n\n"
              f"PRODUCER'S LATEST NOTE\n{body.notes or 'Propose initial ideas.'}\n\n"
              "You are an art director brainstorming square (1:1) podcast episode cover artwork. Respond to the "
              "producer's note and propose 3-4 distinct visual concepts (vary composition, medium and mood). The "
              "art should be reverent, legible as a small thumbnail, and avoid depicting the face of Jesus "
              "realistically unless asked. Return ONLY JSON (no code fences): {\"reply\": \"short conversational "
              "reply\", \"concepts\": [{\"title\": \"\", \"description\": \"1-2 sentences\", \"prompt\": \"a detailed "
              "image-generation prompt including style, palette, lighting, composition; include the episode title "
              "text only if it fits the concept\"}]}")
    try:
        raw = await llm.generate(settings, provider, "You are a creative art director. Reply with JSON only.", prompt)
        data = _parse_json(raw)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Brainstorm failed: {str(e)[:300]}")
    concepts = [{"id": new_id(), "title": str(c.get("title", "")), "description": str(c.get("description", "")),
                 "prompt": str(c.get("prompt", "")), "created_at": now_iso()}
                for c in data.get("concepts") or [] if isinstance(c, dict)]
    ts = now_iso()
    msgs = []
    if body.notes.strip():
        msgs.append({"role": "producer", "content": body.notes.strip(), "by": user["username"], "created_at": ts})
    msgs.append({"role": "assistant", "content": str(data.get("reply", "")), "concept_ids": [c["id"] for c in concepts],
                 "created_at": ts})
    await db.episodes.update_one({"id": ep_id}, {"$set": {
        "artwork.messages": art["messages"] + msgs, "artwork.concepts": art["concepts"] + concepts,
        "artwork.images": art["images"], "artwork.selected_image_id": art["selected_image_id"]}})
    return await _get(ep_id)


async def _openai_image(key: str, model: str, prompt: str) -> bytes:
    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=20.0)) as c:
        r = await c.post("https://api.openai.com/v1/images/generations", headers={"Authorization": f"Bearer {key}"},
                         json={"model": model, "prompt": prompt, "size": "1024x1024", "n": 1})
    if r.status_code >= 400:
        raise RuntimeError(f"OpenAI image error {r.status_code}: {r.text[:500]}")
    item = r.json()["data"][0]
    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"])
    async with httpx.AsyncClient(timeout=60) as c:
        return (await c.get(item["url"])).content


async def _gemini_image(key: str, model: str, prompt: str) -> bytes:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["TEXT", "IMAGE"], "imageConfig": {"aspectRatio": "1:1"}}}
    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=20.0)) as c:
        r = await c.post(url, headers={"x-goog-api-key": key}, json=body)
    if r.status_code >= 400:
        raise RuntimeError(f"Gemini image error {r.status_code}: {r.text[:500]}")
    for part in (r.json().get("candidates") or [{}])[0].get("content", {}).get("parts", []):
        inline = part.get("inlineData") or part.get("inline_data")
        if inline and inline.get("data"):
            return base64.b64decode(inline["data"])
    raise RuntimeError("Gemini returned no image. Try rephrasing the prompt.")


async def save_image_bytes(ep_id: str, data: bytes, meta: dict) -> str:
    img_id = new_id()
    folder = MEDIA_DIR / ep_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{img_id}.png").write_bytes(data)
    ep = await _get(ep_id)
    art = _artwork(ep)
    img = {"id": img_id, "concept_id": None, "created_at": now_iso(), **meta}
    await db.episodes.update_one({"id": ep_id}, {"$set": {
        "artwork.images": art["images"] + [img], "artwork.messages": art["messages"],
        "artwork.concepts": art["concepts"], "artwork.selected_image_id": art["selected_image_id"] or img_id}})
    return img_id


def _sniff(path: Path) -> str:
    head = path.read_bytes()[:12]
    if head.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


async def _run_image(ep_id: str, provider: str, prompt: str, concept_id: str | None, user: dict):
    try:
        s = await llm.get_settings()
        fn = _gemini_image if provider == "gemini" else _openai_image
        data = await fn(s[f"{provider}_api_key"], s[f"{provider}_image_model"], prompt)
        img_id = new_id()
        folder = MEDIA_DIR / ep_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{img_id}.png").write_bytes(data)
        img = {"id": img_id, "prompt": prompt, "concept_id": concept_id, "provider": f"{provider}:{s[f'{provider}_image_model']}",
               "created_by": user["username"], "created_at": now_iso()}
        ep = await _get(ep_id)
        art = _artwork(ep)
        await db.episodes.update_one({"id": ep_id}, {"$set": {
            "artwork.images": art["images"] + [img], "artwork.messages": art["messages"],
            "artwork.concepts": art["concepts"],
            "artwork.selected_image_id": art["selected_image_id"] or img_id,
            "art_generating": None, "art_error": None}})
    except Exception as e:
        log.exception("image generation failed")
        await db.episodes.update_one({"id": ep_id}, {"$set": {"art_generating": None, "art_error": str(e)[:800]}})


@router.post("/episodes/{ep_id}/artwork/generate")
async def generate_artwork(ep_id: str, body: ArtGenIn, user: dict = Depends(get_current_user)):
    ep = await _get(ep_id)
    if not body.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt is empty")
    if ep.get("art_generating"):
        raise HTTPException(status_code=409, detail="Artwork is already being generated")
    s = await llm.get_settings()
    provider = llm.resolve_provider(s, body.provider or s["image_provider"])
    await db.episodes.update_one({"id": ep_id}, {"$set": {
        "art_generating": {"provider": provider, "started_at": now_iso(), "by": user["username"]}, "art_error": None}})
    _spawn(_run_image(ep_id, provider, body.prompt.strip(), body.concept_id, user))
    return await _get(ep_id)


@router.get("/episodes/{ep_id}/artwork/{img_id}.png")
async def artwork_file(ep_id: str, img_id: str, _: dict = Depends(get_current_user)):
    if not re.fullmatch(r"[0-9a-f-]{36}", img_id) or not re.fullmatch(r"[0-9a-f-]{36}", ep_id):
        raise HTTPException(status_code=404, detail="Not found")
    path = MEDIA_DIR / ep_id / f"{img_id}.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path, media_type=_sniff(path), headers={"Cache-Control": "private, max-age=86400"})


@router.post("/episodes/{ep_id}/artwork/{img_id}/select")
async def select_artwork(ep_id: str, img_id: str, _: dict = Depends(get_current_user)):
    ep = await _get(ep_id)
    if not any(i["id"] == img_id for i in _artwork(ep)["images"]):
        raise HTTPException(status_code=404, detail="Image not found")
    await db.episodes.update_one({"id": ep_id}, {"$set": {"artwork.selected_image_id": img_id}})
    return await _get(ep_id)


@router.delete("/episodes/{ep_id}/artwork/{img_id}")
async def delete_artwork(ep_id: str, img_id: str, _: dict = Depends(get_current_user)):
    ep = await _get(ep_id)
    art = _artwork(ep)
    images: List[dict] = [i for i in art["images"] if i["id"] != img_id]
    if len(images) == len(art["images"]):
        raise HTTPException(status_code=404, detail="Image not found")
    (MEDIA_DIR / ep_id / f"{img_id}.png").unlink(missing_ok=True)
    selected = art["selected_image_id"] if art["selected_image_id"] != img_id else (images[-1]["id"] if images else None)
    await db.episodes.update_one({"id": ep_id}, {"$set": {"artwork.images": images, "artwork.selected_image_id": selected}})
    return await _get(ep_id)
