"""Per-user cap on AI actions (each one spends the admin's Gemini/OpenAI key)."""
import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException

from auth import get_current_user
from core import db

WINDOW_SECONDS = 3600


def limit_per_hour() -> int:
    """AI_ACTIONS_PER_HOUR (default 30). 0 turns the cap off."""
    try:
        return int(os.environ.get("AI_ACTIONS_PER_HOUR", "30"))
    except ValueError:
        return 30


async def ai_rate_limit(user: dict = Depends(get_current_user)) -> dict:
    """Dependency for every endpoint that calls an AI provider. Returns the user, or raises 429."""
    limit = limit_per_hour()
    if limit <= 0:
        return user
    now = datetime.now(timezone.utc)
    since = now - timedelta(seconds=WINDOW_SECONDS)
    recent = await db.ai_events.find({"user_id": user["id"], "at": {"$gt": since}}, {"_id": 0, "at": 1}) \
        .sort("at", 1).to_list(limit + 1)
    if len(recent) >= limit:
        wait = max(1, int((recent[0]["at"].replace(tzinfo=timezone.utc) + timedelta(seconds=WINDOW_SECONDS) - now).total_seconds()))
        raise HTTPException(status_code=429, headers={"Retry-After": str(wait)},
                            detail=f"AI limit reached ({limit} actions per hour). Try again in about {max(1, wait // 60)} minute(s).")
    await db.ai_events.insert_one({"user_id": user["id"], "at": now})
    return user
