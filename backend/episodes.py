import asyncio
import logging
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

import llm
import prompts
from auth import get_current_user, require_admin
from bible import BOOKS, books_in, chapter_keys, parse_refs
from core import db, now_iso, new_id, NO_ID
from docx_utils import markdown_to_docx

router = APIRouter(prefix="/episodes", tags=["episodes"])
log = logging.getLogger(__name__)
STATUSES = ["draft", "outline_approved", "script_complete", "published"]
STAGES = ("outline", "script")
LIST_FIELDS = {"_id": 0, "outline_versions": 0, "script_versions": 0, "outline": 0, "script": 0, "assets": 0,
               "artwork.messages": 0, "artwork.concepts": 0}
_tasks = set()


class EpisodeIn(BaseModel):
    title: str = Field(min_length=1)
    episode_number: str = ""
    topic: str = Field(min_length=1)
    primary_scripture: str = Field(min_length=1)
    supporting_scriptures: List[str] = []
    themes: List[str] = []
    target_length: str = ""
    target_date: str = Field(default="", pattern=r"^(\d{4}-\d{2}-\d{2})?$")
    audience_notes: str = ""
    guidance: str = ""


class GenerateIn(BaseModel):
    provider: Optional[str] = None
    notes: str = ""


class ContentIn(BaseModel):
    content: str


class StatusIn(BaseModel):
    status: str


class RestoreIn(BaseModel):
    version: int


BOOK_INDEX = {b: i for i, (b, _) in enumerate(BOOKS)}


def scripture_key(text: str) -> int:
    """Canonical sort key: book order, then chapter; unparseable references sort last."""
    refs = parse_refs(text)
    if not refs:
        return 999_999_999
    book, ch = refs[0]
    verse = re.search(r"\d+\s*:\s*(\d+)", text)
    return BOOK_INDEX[book] * 1_000_000 + (ch or 0) * 1000 + (int(verse.group(1)) if verse else 0)


def _clean_list(items):
    return [i.strip() for i in items if i and i.strip()]


def derive(data: dict) -> dict:
    data["supporting_scriptures"] = _clean_list(data.get("supporting_scriptures", []))
    data["themes"] = _clean_list(data.get("themes", []))
    data["themes_lower"] = [t.lower() for t in data["themes"]]
    refs = [data.get("primary_scripture", "")] + data["supporting_scriptures"]
    data["books"] = books_in(*refs)
    data["chapters"] = chapter_keys(*refs)
    return data


def new_episode(body: dict, user: dict, status="draft") -> dict:
    ts = now_iso()
    return derive({**body, "id": new_id(), "status": status, "outline": "", "script": "",
                   "outline_versions": [], "script_versions": [], "generating": None, "last_error": None,
                   "outline_approved_at": None, "script_completed_at": None, "published_at": None,
                   "created_by": user["username"], "created_at": ts, "updated_at": ts, "imported": False})


async def _get(ep_id: str) -> dict:
    ep = await db.episodes.find_one({"id": ep_id}, NO_ID)
    if not ep:
        raise HTTPException(status_code=404, detail="Episode not found")
    return {k: v for k, v in ep.items() if k != "_id"}


@router.get("")
async def list_episodes(q: str = "", status: str = "", theme: str = "", book: str = "",
                        _: dict = Depends(get_current_user)):
    query = {}
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        query["$or"] = [{"title": rx}, {"topic": rx}, {"primary_scripture": rx}, {"supporting_scriptures": rx},
                        {"themes": rx}, {"episode_number": rx}]
    if status:
        query["status"] = status
    if theme:
        query["themes_lower"] = theme.lower()
    if book:
        query["books"] = book
    eps = await db.episodes.find(query, LIST_FIELDS).sort("created_at", -1).to_list(10000)
    return [{**e, "scripture_key": scripture_key(e.get("primary_scripture", ""))} for e in eps]


@router.get("/meta")
async def meta(_: dict = Depends(get_current_user)):
    eps = await db.episodes.find({}, {"_id": 0, "themes": 1, "books": 1, "status": 1}).to_list(5000)
    themes, books, counts = {}, {}, {s: 0 for s in STATUSES}
    for e in eps:
        counts[e.get("status", "draft")] = counts.get(e.get("status", "draft"), 0) + 1
        for t in e.get("themes") or []:
            themes[t.lower()] = themes.get(t.lower(), 0) + 1
        for b in e.get("books") or []:
            books[b] = books.get(b, 0) + 1
    srt = lambda d: [{"name": k, "count": v} for k, v in sorted(d.items(), key=lambda x: -x[1])]
    return {"total": len(eps), "status_counts": counts, "themes": srt(themes), "books": srt(books)}


@router.get("/similar")
async def similar(scripture: str = "", themes: str = "", topic: str = "", exclude: str = "",
                  _: dict = Depends(get_current_user)):
    chapters = chapter_keys(*scripture.split(";"))
    books = books_in(*scripture.split(";"))
    theme_list = [t.strip().lower() for t in themes.split(",") if t.strip()]
    ors = []
    if chapters:
        ors.append({"chapters": {"$in": chapters}})
    elif books:
        ors.append({"books": {"$in": books}})
    if theme_list:
        ors.append({"themes_lower": {"$in": theme_list}})
    if topic.strip() and len(topic.strip()) >= 4:
        ors.append({"topic": {"$regex": re.escape(topic.strip()), "$options": "i"}})
    if not ors:
        return []
    query = {"$or": ors}
    if exclude:
        query["id"] = {"$ne": exclude}
    results = await db.episodes.find(query, LIST_FIELDS).sort("created_at", -1).to_list(20)
    for r in results:
        reasons = []
        if set(r.get("chapters") or []) & set(chapters):
            reasons.append("Same chapter: " + ", ".join(sorted(set(r["chapters"]) & set(chapters))))
        elif set(r.get("books") or []) & set(books):
            reasons.append("Same book: " + ", ".join(sorted(set(r["books"]) & set(books))))
        shared = set(r.get("themes_lower") or []) & set(theme_list)
        if shared:
            reasons.append("Shared theme: " + ", ".join(sorted(shared)))
        if topic.strip() and topic.strip().lower() in (r.get("topic") or "").lower():
            reasons.append("Similar topic")
        r["reasons"] = reasons
    return results


async def sync_plan_date(ep: dict, user: dict):
    """Keep the episode's planner entry on its target publication date (creates one if needed)."""
    date = ep.get("target_date") or None
    res = await db.plan_items.update_one({"episode_id": ep["id"]}, {"$set": {"date": date}})
    if res.matched_count == 0 and date:
        await db.plan_items.insert_one({
            "id": new_id(), "date": date, "series_id": None, "episode_id": ep["id"], "title": ep["title"],
            "topic": ep.get("topic", ""), "primary_scripture": ep.get("primary_scripture", ""),
            "supporting_scriptures": [], "themes": ep.get("themes", []), "notes": "",
            "created_by": user["username"], "created_at": now_iso()})


@router.post("")
async def create_episode(body: EpisodeIn, user: dict = Depends(get_current_user)):
    doc = new_episode(body.model_dump(), user)
    await db.episodes.insert_one(doc)
    await sync_plan_date(doc, user)
    return await _get(doc["id"])


@router.get("/{ep_id}")
async def get_episode(ep_id: str, _: dict = Depends(get_current_user)):
    return await _get(ep_id)


@router.put("/{ep_id}")
async def update_episode(ep_id: str, body: EpisodeIn, user: dict = Depends(get_current_user)):
    old = await _get(ep_id)
    await db.episodes.update_one({"id": ep_id}, {"$set": {**derive(body.model_dump()), "updated_at": now_iso()}})
    ep = await _get(ep_id)
    if (old.get("target_date") or "") != (ep.get("target_date") or ""):
        await sync_plan_date(ep, user)
    return ep


@router.delete("/{ep_id}")
async def delete_episode(ep_id: str, _: dict = Depends(require_admin)):
    res = await db.episodes.delete_one({"id": ep_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Episode not found")
    await db.plan_items.delete_many({"episode_id": ep_id})
    return {"ok": True}


def _check_editable(ep: dict, stage: str):
    if stage not in STAGES:
        raise HTTPException(status_code=404, detail="Unknown stage")
    if stage == "outline" and ep["status"] != "draft":
        raise HTTPException(status_code=400, detail="Outline is approved and locked. Reopen it to make changes.")
    if stage == "script" and ep["status"] != "outline_approved":
        raise HTTPException(status_code=400, detail="Script can only be edited after outline approval and before completion.")


def _version(ep: dict, stage: str, content: str, source: str, user: dict, notes="", provider=None) -> dict:
    return {"version": len(ep.get(f"{stage}_versions") or []) + 1, "content": content, "source": source,
            "notes": notes, "provider": provider, "created_by": user["username"], "created_at": now_iso()}


async def _run_generation(ep_id: str, stage: str, provider: str, notes: str, user: dict):
    try:
        ep = await _get(ep_id)
        settings = await llm.get_settings()
        ctx = await prompts.reference_context()
        covered = await prompts.covered_summary(ep_id)
        current = ep.get(stage) or None
        build = prompts.outline_prompt if stage == "outline" else prompts.script_prompt
        text = await llm.generate(settings, provider, prompts.system_prompt(settings, ctx),
                                  build(ep, covered, current, notes or None))
        if text.startswith("```"):
            text = re.sub(r"^```[a-z]*\n?|\n?```$", "", text).strip()
        ep = await _get(ep_id)
        source = "ai_revision" if current and notes else "ai"
        model = settings[f"{provider}_model"]
        await db.episodes.update_one({"id": ep_id}, {
            "$set": {stage: text, "generating": None, "last_error": None, "updated_at": now_iso()},
            "$push": {f"{stage}_versions": _version(ep, stage, text, source, user, notes, f"{provider}:{model}")}})
    except Exception as e:  # surfaced to UI through last_error
        log.exception("generation failed")
        await db.episodes.update_one({"id": ep_id}, {"$set": {"generating": None, "last_error": str(e)[:800]}})


@router.post("/{ep_id}/{stage}/generate")
async def generate(ep_id: str, stage: str, body: GenerateIn, user: dict = Depends(get_current_user)):
    ep = await _get(ep_id)
    _check_editable(ep, stage)
    if ep.get("generating"):
        raise HTTPException(status_code=409, detail="A generation is already running for this episode")
    if stage == "script" and not ep.get("outline"):
        raise HTTPException(status_code=400, detail="Approve an outline first")
    settings = await llm.get_settings()
    provider = llm.resolve_provider(settings, body.provider)
    await db.episodes.update_one({"id": ep_id}, {"$set": {
        "generating": {"stage": stage, "provider": provider, "started_at": now_iso(), "by": user["username"]},
        "last_error": None}})
    task = asyncio.create_task(_run_generation(ep_id, stage, provider, body.notes.strip(), user))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return await _get(ep_id)


@router.put("/{ep_id}/{stage}")
async def save_content(ep_id: str, stage: str, body: ContentIn, user: dict = Depends(get_current_user)):
    ep = await _get(ep_id)
    _check_editable(ep, stage)
    if ep.get("generating"):
        raise HTTPException(status_code=409, detail="Wait for the current generation to finish")
    await db.episodes.update_one({"id": ep_id}, {
        "$set": {stage: body.content, "updated_at": now_iso()},
        "$push": {f"{stage}_versions": _version(ep, stage, body.content, "edit", user)}})
    return await _get(ep_id)


@router.post("/{ep_id}/{stage}/restore")
async def restore_version(ep_id: str, stage: str, body: RestoreIn, user: dict = Depends(get_current_user)):
    ep = await _get(ep_id)
    _check_editable(ep, stage)
    match = next((v for v in ep.get(f"{stage}_versions") or [] if v["version"] == body.version), None)
    if not match:
        raise HTTPException(status_code=404, detail="Version not found")
    await db.episodes.update_one({"id": ep_id}, {
        "$set": {stage: match["content"], "updated_at": now_iso()},
        "$push": {f"{stage}_versions": _version(ep, stage, match["content"], "restore", user,
                                                f"Restored from v{body.version}")}})
    return await _get(ep_id)


TRANSITIONS = {
    "outline_approved": ({"draft", "script_complete"}, "outline"),
    "draft": ({"outline_approved", "script_complete"}, None),
    "script_complete": ({"outline_approved", "published"}, "script"),
    "published": ({"script_complete"}, "script"),
}
STAMP = {"outline_approved": "outline_approved_at", "script_complete": "script_completed_at",
         "published": "published_at"}


@router.post("/{ep_id}/status")
async def set_status(ep_id: str, body: StatusIn, _: dict = Depends(get_current_user)):
    ep = await _get(ep_id)
    if body.status not in TRANSITIONS:
        raise HTTPException(status_code=400, detail="Unknown status")
    allowed, needs = TRANSITIONS[body.status]
    if ep["status"] not in allowed:
        raise HTTPException(status_code=400, detail=f"Cannot move from {ep['status']} to {body.status}")
    if needs and not (ep.get(needs) or "").strip():
        raise HTTPException(status_code=400, detail=f"The {needs} is empty")
    if ep.get("generating"):
        raise HTTPException(status_code=409, detail="Wait for the current generation to finish")
    changes = {"status": body.status, "updated_at": now_iso()}
    if body.status in STAMP and STATUSES.index(body.status) > STATUSES.index(ep["status"]):
        changes[STAMP[body.status]] = now_iso()
    await db.episodes.update_one({"id": ep_id}, {"$set": changes})
    return await _get(ep_id)


@router.get("/{ep_id}/export/{stage}.docx")
async def export_docx(ep_id: str, stage: str, _: dict = Depends(get_current_user)):
    if stage not in STAGES:
        raise HTTPException(status_code=404, detail="Unknown stage")
    ep = await _get(ep_id)
    if not (ep.get(stage) or "").strip():
        raise HTTPException(status_code=400, detail=f"No {stage} to export")
    settings = await llm.get_settings()
    num = f"Episode {ep['episode_number']} · " if ep.get("episode_number") else ""
    meta = [f"{settings['show_name']} · {num}{stage.title()}", f"Scripture: {ep['primary_scripture']}"]
    if ep.get("themes"):
        meta.append("Themes: " + ", ".join(ep["themes"]))
    data = markdown_to_docx(ep["title"], meta, ep[stage])
    safe = re.sub(r"[^A-Za-z0-9]+", "-", ep["title"]).strip("-")[:60] or "episode"
    return Response(content=data, headers={"Content-Disposition": f'attachment; filename="{safe}-{stage}.docx"'},
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
