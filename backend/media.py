"""Single place that builds filesystem paths under MEDIA_DIR.

Every path is built from validated UUID segments and then resolved and checked to
still be inside MEDIA_DIR, so a request value can never escape the media folder.
"""
import os
import re
from pathlib import Path

from fastapi import HTTPException

MEDIA_DIR = Path(os.environ["MEDIA_DIR"])
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def is_image(data: bytes) -> bool:
    """True only for real PNG, JPEG or WebP data (checks the file's own signature, not the claimed type)."""
    return (data.startswith(b"\x89PNG\r\n\x1a\n") or data.startswith(b"\xff\xd8\xff")
            or (data[:4] == b"RIFF" and data[8:12] == b"WEBP"))


def _safe(*segments: str) -> Path:
    root = os.path.realpath(MEDIA_DIR)
    full = os.path.realpath(os.path.join(root, *segments))
    if not full.startswith(root + os.sep):
        raise HTTPException(status_code=404, detail="Not found")
    return Path(full)


def _uuid(value: str) -> str:
    if not isinstance(value, str) or not _UUID.fullmatch(value):
        raise HTTPException(status_code=404, detail="Not found")
    return value


def episode_dir(ep_id: str) -> Path:
    return _safe(_uuid(ep_id))


def episode_image_path(ep_id: str, img_id: str) -> Path:
    return _safe(_uuid(ep_id), _uuid(img_id) + ".png")


def series_dir(series_id: str) -> Path:
    return _safe("series", _uuid(series_id))


def series_image_path(series_id: str, img_id: str) -> Path:
    return _safe("series", _uuid(series_id), _uuid(img_id) + ".png")
