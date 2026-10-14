import os
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
PRESERVE = ["settings", "users", "episodes", "documents", "series", "plan_items", "rss_items", "rss_jobs",
            "coverage_suggestions"]
_snapshot = {}


def _is_controller(config) -> bool:
    # xdist workers have workerinput; the controller (or a non-xdist run) does not
    return not hasattr(config, "workerinput")


def _db():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def pytest_configure(config):
    """Snapshot real data once, before any worker starts, so fake keys/wipes from tests never persist."""
    if _is_controller(config):
        db = _db()
        _snapshot.update({c: list(db[c].find({})) for c in PRESERVE})


def pytest_unconfigure(config):
    if _is_controller(config) and _snapshot:
        db = _db()
        for c, docs in _snapshot.items():
            db[c].delete_many({})
            if docs:
                db[c].insert_many(docs)
