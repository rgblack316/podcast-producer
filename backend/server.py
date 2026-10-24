from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import logging  # noqa: E402
import os  # noqa: E402
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.middleware.cors import CORSMiddleware  # noqa: E402

from admin import docs_router, settings_router  # noqa: E402
from auth import router as auth_router, seed_admin, users_router  # noqa: E402
from core import client, db  # noqa: E402
from episodes import router as episodes_router  # noqa: E402
from extras import router as extras_router  # noqa: E402
from planner import router as planner_router  # noqa: E402
from rss_import import router as rss_router  # noqa: E402
from setup import router as setup_router  # noqa: E402
from series_art import router as series_art_router  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

app = FastAPI(title="Bible Bytes Producer")
api = APIRouter(prefix="/api")


@api.get("/health")
async def health():
    return {"ok": True}


for r in (auth_router, users_router, setup_router, series_art_router, extras_router, planner_router, rss_router, episodes_router, settings_router, docs_router):
    api.include_router(r)
app.include_router(api)

origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip() and o.strip() != "*"]
if origins:
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def startup():
    await db.users.create_index("username", unique=True)
    await db.users.create_index("id", unique=True)
    await db.episodes.create_index("id", unique=True)
    await db.episodes.create_index([("created_at", -1)])
    await db.documents.create_index("id", unique=True)
    await db.login_attempts.create_index("identifier")
    # Encrypt any AI keys saved before encryption existed
    from secrets_box import KEY_FIELDS, encrypt
    cur = await db.settings.find_one({"id": "app"}, {"_id": 0})
    if cur:
        fix = {k: encrypt(cur[k]) for k in KEY_FIELDS if cur.get(k) and not cur[k].startswith("enc1:")}
        if fix:
            await db.settings.update_one({"id": "app"}, {"$set": fix})
    await db.ai_events.create_index("user_id")
    await db.ai_events.create_index("at", expireAfterSeconds=3600)
    await db.revoked_tokens.create_index("jti", unique=True)
    await db.revoked_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.episodes.update_many({"generating": {"$ne": None}},
                                  {"$set": {"generating": None, "last_error": "Generation interrupted by a server restart"}})
    await db.episodes.update_many({"art_generating": {"$ne": None}},
                                  {"$set": {"art_generating": None, "art_error": "Generation interrupted by a server restart"}})
    await db.rss_items.create_index("guid", unique=True)
    await db.rss_jobs.update_many({"running": True}, {"$set": {"running": False}})
    await seed_admin()


@app.on_event("shutdown")
async def shutdown():
    client.close()
