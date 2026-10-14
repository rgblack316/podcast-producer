import re
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import get_current_user
from core import db, now_iso, new_id, NO_ID

router = APIRouter(tags=["planner"])
DATE_RX = r"^\d{4}-\d{2}-\d{2}$"
EP_FIELDS = {"_id": 0, "id": 1, "title": 1, "episode_number": 1, "status": 1, "primary_scripture": 1, "topic": 1, "themes": 1}


class SeriesIn(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""
    color: str = Field(default="#B45309", pattern=r"^#[0-9A-Fa-f]{6}$")


@router.get("/series")
async def list_series(_: dict = Depends(get_current_user)):
    series = await db.series.find({}, NO_ID).sort("created_at", 1).to_list(500)
    out = []
    for s in series:
        out.append({**{k: v for k, v in s.items() if k != "_id"},
                    "count": await db.plan_items.count_documents({"series_id": s["id"]})})
    return out


@router.post("/series")
async def create_series(body: SeriesIn, user: dict = Depends(get_current_user)):
    doc = {**body.model_dump(), "id": new_id(), "created_by": user["username"], "created_at": now_iso()}
    await db.series.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


@router.put("/series/{series_id}")
async def update_series(series_id: str, body: SeriesIn, _: dict = Depends(get_current_user)):
    res = await db.series.update_one({"id": series_id}, {"$set": body.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Series not found")
    s = await db.series.find_one({"id": series_id}, NO_ID)
    return {k: v for k, v in s.items() if k != "_id"}


@router.delete("/series/{series_id}")
async def delete_series(series_id: str, _: dict = Depends(get_current_user)):
    res = await db.series.delete_one({"id": series_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Series not found")
    await db.plan_items.update_many({"series_id": series_id}, {"$set": {"series_id": None}})
    return {"ok": True}


class PlanIn(BaseModel):
    date: Optional[str] = Field(default=None, pattern=DATE_RX)
    series_id: Optional[str] = None
    episode_id: Optional[str] = None
    title: str = ""
    topic: str = ""
    primary_scripture: str = ""
    supporting_scriptures: List[str] = []
    themes: List[str] = []
    notes: str = ""


class PlanPatch(BaseModel):
    date: Optional[str] = None
    series_id: Optional[str] = None
    episode_id: Optional[str] = None
    title: Optional[str] = None
    notes: Optional[str] = None


async def _hydrate(items: list) -> list:
    ids = [i["episode_id"] for i in items if i.get("episode_id")]
    eps = {e["id"]: e for e in await db.episodes.find({"id": {"$in": ids}}, EP_FIELDS).to_list(5000)} if ids else {}
    for i in items:
        i["episode"] = eps.get(i.get("episode_id"))
    return items


@router.get("/plan")
async def list_plan(start: str = "", end: str = "", _: dict = Depends(get_current_user)):
    q = {}
    if start and end:
        q = {"$or": [{"date": {"$gte": start, "$lte": end}}, {"date": None}]}
    items = await db.plan_items.find(q, NO_ID).sort("date", 1).to_list(2000)
    return await _hydrate(items)


@router.post("/plan")
async def create_plan(body: PlanIn, user: dict = Depends(get_current_user)):
    data = body.model_dump()
    if data["episode_id"]:
        ep = await db.episodes.find_one({"id": data["episode_id"]}, EP_FIELDS)
        if not ep:
            raise HTTPException(status_code=404, detail="Episode not found")
        if await db.plan_items.find_one({"episode_id": data["episode_id"]}, {"_id": 1}):
            raise HTTPException(status_code=400, detail="That episode is already on the plan")
        data["title"] = data["title"] or ep["title"]
    if not data["title"].strip():
        raise HTTPException(status_code=400, detail="Title is required")
    doc = {**data, "id": new_id(), "created_by": user["username"], "created_at": now_iso()}
    await db.plan_items.insert_one(doc)
    return (await _hydrate([{k: v for k, v in doc.items() if k != "_id"}]))[0]


@router.patch("/plan/{item_id}")
async def patch_plan(item_id: str, body: PlanPatch, _: dict = Depends(get_current_user)):
    changes = body.model_dump(exclude_unset=True)
    if changes.get("date") and not re.match(DATE_RX, changes["date"]):
        raise HTTPException(status_code=400, detail="Date must be YYYY-MM-DD")
    res = await db.plan_items.update_one({"id": item_id}, {"$set": changes})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Plan item not found")
    return (await _hydrate([await db.plan_items.find_one({"id": item_id}, NO_ID)]))[0]


@router.delete("/plan/{item_id}")
async def delete_plan(item_id: str, _: dict = Depends(get_current_user)):
    res = await db.plan_items.delete_one({"id": item_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Plan item not found")
    return {"ok": True}
