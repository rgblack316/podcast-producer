import os
import re
from datetime import datetime, timezone, timedelta
from typing import Optional

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from core import db, now_iso, new_id, NO_ID

JWT_ALGORITHM = "HS256"
ACCESS_MINUTES = 30
REFRESH_DAYS = 7
MAX_ATTEMPTS = 5
MAX_USER_ATTEMPTS = 20  # per username across all IPs: backstop against distributed or spoofed-IP guessing
LOCKOUT_MINUTES = 15
USER_PUBLIC = {"_id": 0, "password_hash": 0, "mfa_secret": 0}

router = APIRouter(prefix="/auth", tags=["auth"])


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def _secret() -> str:
    return os.environ["JWT_SECRET"]


def _token(user_id: str, kind: str, delta: timedelta) -> str:
    payload = {"sub": user_id, "type": kind, "exp": datetime.now(timezone.utc) + delta}
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def _cookie_secure() -> bool:
    return os.environ.get("COOKIE_SECURE", "true").lower() == "true"


def set_auth_cookies(response: Response, user_id: str):
    opts = dict(httponly=True, secure=_cookie_secure(), samesite="lax", path="/")
    response.set_cookie("access_token", _token(user_id, "access", timedelta(minutes=ACCESS_MINUTES)),
                        max_age=ACCESS_MINUTES * 60, **opts)
    response.set_cookie("refresh_token", _token(user_id, "refresh", timedelta(days=REFRESH_DAYS)),
                        max_age=REFRESH_DAYS * 86400, **opts)


def _decode(token: str, kind: str) -> str:
    try:
        payload = jwt.decode(token, _secret(), algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    if payload.get("type") != kind:
        raise HTTPException(status_code=401, detail="Invalid token type")
    return payload["sub"]


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        header = request.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            token = header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = await db.users.find_one({"id": _decode(token, "access")}, USER_PUBLIC)
    if not user or not user.get("active", True):
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


class LoginIn(BaseModel):
    username: str
    password: str


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


def _client_ip(request: Request) -> str:
    # Never read client-supplied headers here. nginx overwrites X-Forwarded-For with the verified peer address
    # and uvicorn (--proxy-headers) copies it into request.client.
    return request.client.host if request.client else "unknown"


async def _is_locked(identifier: str) -> bool:
    attempt = await db.login_attempts.find_one({"identifier": identifier}, NO_ID)
    return bool(attempt and attempt.get("locked_until") and attempt["locked_until"] > now_iso())


async def _record_failure(identifier: str, limit: int):
    attempt = await db.login_attempts.find_one({"identifier": identifier}, NO_ID)
    count = (attempt or {}).get("count", 0) + 1
    update = {"identifier": identifier, "count": count, "updated_at": now_iso()}
    if count >= limit:
        update["locked_until"] = (datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()
        update["count"] = 0
    await db.login_attempts.update_one({"identifier": identifier}, {"$set": update}, upsert=True)


@router.post("/login")
async def login(body: LoginIn, request: Request, response: Response):
    username = body.username.strip().lower()
    identifier = f"{_client_ip(request)}:{username}"
    user_identifier = f"user:{username}"
    if await _is_locked(identifier) or await _is_locked(user_identifier):
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 15 minutes.")

    user = await db.users.find_one({"username": username}, {"_id": 0})
    if not user or not user.get("active", True) or not verify_password(body.password, user["password_hash"]):
        await _record_failure(identifier, MAX_ATTEMPTS)
        await _record_failure(user_identifier, MAX_USER_ATTEMPTS)
        raise HTTPException(status_code=401, detail="Invalid username or password")

    await db.login_attempts.delete_many({"identifier": {"$in": [identifier, user_identifier]}})
    # MFA hook: when user["mfa_enabled"] is true, a TOTP challenge step will be inserted here (Phase 2).
    await db.users.update_one({"id": user["id"]}, {"$set": {"last_login_at": now_iso()}})
    set_auth_cookies(response, user["id"])
    return await db.users.find_one({"id": user["id"]}, USER_PUBLIC)


@router.post("/refresh")
async def refresh(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    user = await db.users.find_one({"id": _decode(token, "refresh")}, USER_PUBLIC)
    if not user or not user.get("active", True):
        raise HTTPException(status_code=401, detail="User not found or inactive")
    set_auth_cookies(response, user["id"])
    return user


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"ok": True}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@router.post("/change-password")
async def change_password(body: ChangePasswordIn, user: dict = Depends(get_current_user)):
    full = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    if not verify_password(body.current_password, full["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    await db.users.update_one({"id": user["id"]}, {"$set": {"password_hash": hash_password(body.new_password)}})
    return {"ok": True}


# ---------- Admin user management ----------
users_router = APIRouter(prefix="/users", tags=["users"])


class UserCreate(BaseModel):
    username: str = Field(min_length=3)
    name: str = ""
    password: str = Field(min_length=8)
    role: str = Field(default="producer", pattern="^(admin|producer)$")


class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = Field(default=None, pattern="^(admin|producer)$")
    active: Optional[bool] = None


class ResetPasswordIn(BaseModel):
    new_password: str = Field(min_length=8)


def user_doc(username: str, name: str, password: str, role: str) -> dict:
    return {
        "id": new_id(), "username": username.strip().lower(), "name": name or username,
        "password_hash": hash_password(password), "role": role, "active": True,
        "mfa_enabled": False, "mfa_secret": None, "created_at": now_iso(), "last_login_at": None,
    }


@users_router.get("")
async def list_users(_: dict = Depends(require_admin)):
    return await db.users.find({}, USER_PUBLIC).sort("created_at", 1).to_list(500)


@users_router.post("")
async def create_user(body: UserCreate, _: dict = Depends(require_admin)):
    if await db.users.find_one({"username": body.username.strip().lower()}):
        raise HTTPException(status_code=400, detail="Username already exists")
    doc = user_doc(body.username, body.name, body.password, body.role)
    await db.users.insert_one(doc)
    return await db.users.find_one({"id": doc["id"]}, USER_PUBLIC)


@users_router.patch("/{user_id}")
async def update_user(user_id: str, body: UserUpdate, admin: dict = Depends(require_admin)):
    changes = body.model_dump(exclude_none=True)
    if user_id == admin["id"] and (changes.get("active") is False or changes.get("role") == "producer"):
        raise HTTPException(status_code=400, detail="You cannot deactivate or demote your own account")
    if changes:
        await db.users.update_one({"id": user_id}, {"$set": changes})
    user = await db.users.find_one({"id": user_id}, USER_PUBLIC)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@users_router.post("/{user_id}/reset-password")
async def reset_password(user_id: str, body: ResetPasswordIn, _: dict = Depends(require_admin)):
    res = await db.users.update_one({"id": user_id}, {"$set": {"password_hash": hash_password(body.new_password)}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True}


@users_router.delete("/{user_id}")
async def delete_user(user_id: str, admin: dict = Depends(require_admin)):
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    user = await db.users.find_one({"id": user_id}, USER_PUBLIC)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user["role"] == "admin" and await db.users.count_documents({"role": "admin", "active": True, "id": {"$ne": user_id}}) == 0:
        raise HTTPException(status_code=400, detail="At least one active admin must remain")
    await db.users.delete_one({"id": user_id})
    await db.login_attempts.delete_many({"identifier": {"$regex": f":{re.escape(user['username'])}$"}})
    return {"ok": True}


async def seed_admin():
    """Optional: seed/recover an admin from env. Without it, the first-run setup wizard creates the admin."""
    username = os.environ.get("ADMIN_USERNAME", "").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD", "")
    if not username or not password:
        return
    existing = await db.users.find_one({"username": username})
    if existing is None:
        await db.users.insert_one(user_doc(username, "Administrator", password, "admin"))
    elif os.environ.get("ADMIN_FORCE_RESET", "false").lower() == "true":
        await db.users.update_one({"username": username}, {"$set": {
            "password_hash": hash_password(password), "active": True, "role": "admin"}})
