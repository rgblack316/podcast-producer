"""End-to-end smoke test of the real app (routing, cookies, auth, setup, backup) against an in-memory Mongo.
Catches breakage from FastAPI/Starlette/Motor upgrades."""
import os
import subprocess
import sys

import pytest

pytest.importorskip("mongomock_motor")


def test_app_smoke():
    here = os.path.dirname(__file__)
    r = subprocess.run([sys.executable, os.path.join(here, "_smoke_run.py")], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0 and "SMOKE OK" in r.stdout, r.stdout[-2000:] + r.stderr[-3000:]
