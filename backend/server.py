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

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

app = FastAPI(title="Bible Bytes Producer")
api = APIRouter(prefix="/api")


@api.get("/health")
async def health():
    return {"ok": True}


for r in (auth_router, users_router, episodes_router, settings_router, docs_router):
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
    await db.episodes.update_many({"generating": {"$ne": None}},
                                  {"$set": {"generating": None, "last_error": "Generation interrupted by a server restart"}})
    await seed_admin()


@app.on_event("shutdown")
async def shutdown():
    client.close()
