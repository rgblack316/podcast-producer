"""Security audit trail: who signed in, failed to, changed users/settings, took or restored backups.
Never records passwords, tokens or API key values. Entries expire after AUDIT_RETENTION_DAYS (default 365)."""
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import Request

from core import db

log = logging.getLogger("audit")


def retention_seconds() -> int:
    try:
        return max(1, int(os.environ.get("AUDIT_RETENTION_DAYS", "365"))) * 86400
    except ValueError:
        return 365 * 86400


async def audit(request: Optional[Request], action: str, actor: Optional[dict] = None, target: str = "", **detail):
    """Best effort: a failure to log must never break the request."""
    try:
        await db.audit_log.insert_one({
            "at": datetime.now(timezone.utc), "action": action,
            "actor": (actor or {}).get("username", ""), "actor_id": (actor or {}).get("id", ""),
            "target": target, "ip": request.client.host if request is not None and request.client else "",
            "detail": detail})
    except Exception:  # noqa: BLE001
        log.exception("could not write audit entry %s", action)
