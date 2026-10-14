import os
from pathlib import Path

import pytest
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
PRESERVE = ["settings", "users", "episodes", "documents", "series", "plan_items", "rss_items", "rss_jobs",
            "coverage_suggestions"]


@pytest.fixture(scope="session", autouse=True)
def preserve_real_data():
    """Tests write fake API keys and wipe collections; snapshot the real data and put it back afterwards."""
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    snapshot = {c: list(db[c].find({})) for c in PRESERVE}
    yield
    for c, docs in snapshot.items():
        db[c].delete_many({})
        if docs:
            db[c].insert_many(docs)
