"""Encrypts the AI provider keys stored in MongoDB, so a database dump or file copy doesn't expose them.

The encryption key is derived from JWT_SECRET (which lives only in .env). If JWT_SECRET is ever changed the
stored keys can't be read any more; they're treated as unset and an admin simply re-enters them in Settings.
"""
import base64
import hashlib
import logging
import os

from cryptography.fernet import Fernet, InvalidToken

log = logging.getLogger("secrets_box")
PREFIX = "enc1:"
KEY_FIELDS = ("gemini_api_key", "openai_api_key")


def _fernet() -> Fernet:
    raw = hashlib.sha256(b"podcast-producer/settings-keys/v1:" + os.environ["JWT_SECRET"].encode()).digest()
    return Fernet(base64.urlsafe_b64encode(raw))


def encrypt(value: str) -> str:
    if not value or value.startswith(PREFIX):
        return value
    return PREFIX + _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    """Plaintext values (from before encryption existed) pass through unchanged."""
    if not value or not value.startswith(PREFIX):
        return value
    try:
        return _fernet().decrypt(value[len(PREFIX):].encode()).decode()
    except InvalidToken:
        log.warning("Could not decrypt a stored API key (JWT_SECRET changed?). Re-enter it in Settings.")
        return ""
