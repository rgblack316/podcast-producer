import asyncio
import html
import json
import logging
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import llm
import prompts
from auth import require_admin
from core import db, now_iso, new_id, NO_ID
from episodes import new_episode

router = APIRouter(prefix="/rss", tags=["rss"])
log = logging.getLogger(__name__)
NS = {"itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd", "podcast": "https://podcastindex.org/namespace/1.0",
      "content": "http://purl.org/rss/1.0/modules/content/"}
LIST_FIELDS = {"_id": 0, "content": 0, "description": 0}
_tasks = set()
CONCURRENCY = 3
UA = {"User-Agent": "BibleBytesProducer/1.0 (+self-hosted)"}


def strip_html(s: str) -> str:
    s = re.sub(r"<(br|/p|/div|/li|/h\d)[^>]*>", "\n", s or "", flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{3,}", "\n\n", html.unescape(s)).strip()


def _text(el, path):
    found = el.find(path, NS)
    return (found.text or "").strip() if found is not None and found.text else ""


def _episode_number(item, title: str) -> str:
    n = _text(item, "itunes:episode")
    if n:
        return n
    m = re.search(r"(?:\bep(?:isode)?\.?\s*|#)(\d{1,4})\b", title, re.I)
    return m.group(1) if m else ""


def parse_feed(xml_bytes: bytes) -> list:
    root = ET.fromstring(xml_bytes)
    items = []
    for it in root.iter("item"):
        title = _text(it, "title")
        guid = _text(it, "guid") or _text(it, "link") or title
        pub = _text(it, "pubDate")
        try:
            pub_iso = parsedate_to_datetime(pub).isoformat() if pub else None
        except (TypeError, ValueError):
            pub_iso = None
        transcripts = [{"url": t.get("url"), "type": (t.get("type") or "").lower()}
                       for t in it.findall("podcast:transcript", NS) if t.get("url")]
        enclosure = it.find("enclosure")
        items.append({
            "guid": guid, "title": title, "published_at": pub_iso, "episode_number": _episode_number(it, title),
            "season": _text(it, "itunes:season"),
            "description": strip_html(_text(it, "content:encoded") or _text(it, "description") or _text(it, "itunes:summary")),
            "link": _text(it, "link"), "audio_url": enclosure.get("url") if enclosure is not None else "",
            "transcripts": transcripts,
        })
    return items


def transcript_to_text(body: str, ctype: str) -> str:
    if "json" in ctype:
        try:
            data = json.loads(body)
            return " ".join(s.get("body", "") for s in data.get("segments", [])).strip()
        except ValueError:
            return ""
    if "vtt" in ctype or "srt" in ctype or "-->" in body[:2000]:
        lines = [ln.strip() for ln in body.splitlines()]
        keep = [ln for ln in lines if ln and "-->" not in ln and not ln.isdigit() and ln != "WEBVTT"
                and not ln.startswith(("NOTE", "STYLE"))]
        return re.sub(r"<[^>]+>", "", " ".join(keep))
    if "html" in ctype:
        return strip_html(body)
    return body.strip()


async def fetch_transcript(client: httpx.AsyncClient, transcripts: list) -> str:
    order = sorted(transcripts, key=lambda t: 0 if "text/plain" in t["type"] else 1 if "vtt" in t["type"] or "srt" in t["type"] else 2)
    for t in order:
        try:
            r = await client.get(t["url"], follow_redirects=True)
            if r.status_code < 400:
                text = transcript_to_text(r.text, t["type"] or r.headers.get("content-type", ""))
                if len(text) > 200:
                    return text
        except httpx.HTTPError:
            continue
    return ""


class FetchIn(BaseModel):
    feed_url: Optional[str] = None


@router.post("/fetch")
async def fetch_feed(body: FetchIn, admin: dict = Depends(require_admin)):
    s = await llm.get_settings()
    url = (body.feed_url or s.get("rss_feed_url") or "").strip()
    if not re.match(r"^https?://", url):
        raise HTTPException(status_code=400, detail="Enter a valid RSS feed URL (http/https)")
    if body.feed_url:
        await db.settings.update_one({"id": "app"}, {"$set": {"rss_feed_url": url}}, upsert=True)
    try:
        async with httpx.AsyncClient(timeout=60, headers=UA) as c:
            r = await c.get(url, follow_redirects=True)
        r.raise_for_status()
        items = parse_feed(r.content)
    except (httpx.HTTPError, ET.ParseError) as e:
        raise HTTPException(status_code=400, detail=f"Could not read the feed: {str(e)[:300]}")
    imported_guids = set(await db.episodes.distinct("rss_guid"))
    await db.rss_items.delete_many({"feed_url": {"$ne": url}, "status": {"$ne": "imported"}})
    added = 0
    for it in items:
        it["feed_url"] = url
        existing = await db.rss_items.find_one({"guid": it["guid"]}, {"_id": 0, "id": 1})
        if existing:
            await db.rss_items.update_one({"guid": it["guid"]}, {"$set": {**it, "fetched_at": now_iso()}})
            continue
        status = "imported" if it["guid"] in imported_guids else "new"
        await db.rss_items.insert_one({**it, "id": new_id(), "status": status, "content": "", "content_source": None,
                                       "suggestion": None, "error": None, "episode_id": None, "fetched_at": now_iso()})
        added += 1
    return {"total": len(items), "added": added}


async def _analyze_one(item: dict, settings: dict, provider: str, client: httpx.AsyncClient):
    content, source = "", "description"
    if item.get("transcripts"):
        content = await fetch_transcript(client, item["transcripts"])
        if content:
            source = "transcript"
    if not content:
        content = item.get("description") or ""
    text = f"Feed title: {item['title']}\nEpisode number: {item.get('episode_number') or 'unknown'}\n\n{content}"
    raw = await llm.generate(settings, provider, "You extract structured metadata and reply with JSON only.",
                             prompts.metadata_prompt(text))
    m = re.search(r"\{.*\}", raw, re.S)
    data = json.loads(m.group(0) if m else raw)
    return content, source, {
        "title": str(data.get("title") or item["title"]),
        "episode_number": str(data.get("episode_number") or item.get("episode_number") or ""),
        "topic": str(data.get("topic", "")), "primary_scripture": str(data.get("primary_scripture", "")),
        "supporting_scriptures": [str(x) for x in data.get("supporting_scriptures") or []],
        "themes": [str(x) for x in data.get("themes") or []]}


async def _run_analysis(ids: list, provider: str):
    settings = await llm.get_settings()
    sem = asyncio.Semaphore(CONCURRENCY)
    async with httpx.AsyncClient(timeout=60, headers=UA) as client:
        async def work(item_id):
            async with sem:
                item = await db.rss_items.find_one({"id": item_id}, NO_ID)
                if not item:
                    return
                try:
                    content, source, sug = await _analyze_one(item, settings, provider, client)
                    await db.rss_items.update_one({"id": item_id}, {"$set": {
                        "content": content, "content_source": source, "suggestion": sug, "status": "review", "error": None}})
                    await db.rss_jobs.update_one({"id": "current"}, {"$inc": {"done": 1}})
                except Exception as e:
                    await db.rss_items.update_one({"id": item_id}, {"$set": {"error": str(e)[:300]}})
                    await db.rss_jobs.update_one({"id": "current"}, {"$inc": {"done": 1, "errors": 1}})
        await asyncio.gather(*(work(i) for i in ids))
    await db.rss_jobs.update_one({"id": "current"}, {"$set": {"running": False, "finished_at": now_iso()}})


class AnalyzeIn(BaseModel):
    ids: List[str] = []
    provider: Optional[str] = None


@router.post("/analyze")
async def analyze(body: AnalyzeIn, _: dict = Depends(require_admin)):
    job = await db.rss_jobs.find_one({"id": "current"}, NO_ID)
    if job and job.get("running"):
        raise HTTPException(status_code=409, detail="An analysis is already running")
    settings = await llm.get_settings()
    provider = llm.resolve_provider(settings, body.provider)
    query = {"id": {"$in": body.ids}} if body.ids else {"status": "new"}
    ids = [d["id"] for d in await db.rss_items.find(query, {"_id": 0, "id": 1}).to_list(5000)]
    if not ids:
        raise HTTPException(status_code=400, detail="Nothing to analyze")
    await db.rss_jobs.update_one({"id": "current"}, {"$set": {
        "running": True, "total": len(ids), "done": 0, "errors": 0, "provider": provider,
        "started_at": now_iso(), "finished_at": None}}, upsert=True)
    t = asyncio.create_task(_run_analysis(ids, provider))
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)
    job = await db.rss_jobs.find_one({"id": "current"}, NO_ID)
    return {k: v for k, v in (job or {}).items() if k != "_id"}


@router.get("/job")
async def job_status(_: dict = Depends(require_admin)):
    job = await db.rss_jobs.find_one({"id": "current"}, NO_ID)
    return {k: v for k, v in job.items() if k != "_id"} if job else {"running": False, "total": 0, "done": 0, "errors": 0}


@router.get("/items")
async def list_items(status: str = "", _: dict = Depends(require_admin)):
    q = {"status": status} if status else {}
    items = await db.rss_items.find(q, LIST_FIELDS).sort("published_at", -1).to_list(5000)
    counts = {}
    for d in await db.rss_items.find({}, {"_id": 0, "status": 1}).to_list(5000):
        counts[d["status"]] = counts.get(d["status"], 0) + 1
    s = await llm.get_settings()
    return {"items": items, "counts": counts, "feed_url": s.get("rss_feed_url", "")}


@router.get("/items/{item_id}")
async def get_item(item_id: str, _: dict = Depends(require_admin)):
    item = await db.rss_items.find_one({"id": item_id}, NO_ID)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return {k: v for k, v in item.items() if k != "_id"}


class SuggestionIn(BaseModel):
    title: str
    episode_number: str = ""
    topic: str = ""
    primary_scripture: str = ""
    supporting_scriptures: List[str] = []
    themes: List[str] = []


@router.put("/items/{item_id}/suggestion")
async def update_suggestion(item_id: str, body: SuggestionIn, _: dict = Depends(require_admin)):
    res = await db.rss_items.update_one({"id": item_id, "status": {"$ne": "imported"}},
                                        {"$set": {"suggestion": body.model_dump(), "status": "review"}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Item not found or already imported")
    return await get_item(item_id, _)


class IdsIn(BaseModel):
    ids: List[str]


@router.post("/items/skip")
async def skip_items(body: IdsIn, _: dict = Depends(require_admin)):
    await db.rss_items.update_many({"id": {"$in": body.ids}, "status": {"$ne": "imported"}}, {"$set": {"status": "skipped"}})
    return {"ok": True}


@router.post("/items/unskip")
async def unskip_items(body: IdsIn, _: dict = Depends(require_admin)):
    for d in await db.rss_items.find({"id": {"$in": body.ids}, "status": "skipped"}, NO_ID).to_list(5000):
        await db.rss_items.update_one({"id": d["id"]}, {"$set": {"status": "review" if d.get("suggestion") else "new"}})
    return {"ok": True}


@router.post("/items/import")
async def import_items(body: IdsIn, admin: dict = Depends(require_admin)):
    imported, skipped = 0, []
    for d in await db.rss_items.find({"id": {"$in": body.ids}}, NO_ID).to_list(5000):
        sug = d.get("suggestion") or {}
        if d["status"] == "imported" or not sug.get("topic") or not sug.get("primary_scripture"):
            skipped.append(d["title"])
            continue
        if await db.episodes.find_one({"rss_guid": d["guid"]}, {"_id": 1}):
            await db.rss_items.update_one({"id": d["id"]}, {"$set": {"status": "imported"}})
            skipped.append(d["title"])
            continue
        ep = new_episode({**sug, "target_length": "", "audience_notes": "", "guidance": ""}, admin, status="published")
        ep.update({"script": d.get("content") or d.get("description") or "", "imported": True, "rss_guid": d["guid"],
                   "rss_content_source": d.get("content_source"), "audio_url": d.get("audio_url"),
                   "published_at": d.get("published_at") or now_iso()})
        await db.episodes.insert_one(ep)
        await db.rss_items.update_one({"id": d["id"]}, {"$set": {"status": "imported", "episode_id": ep["id"]}})
        imported += 1
    return {"imported": imported, "skipped": skipped}
