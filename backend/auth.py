import os
import re
from datetime import datetime, timezone, timedelta
from typing import Optional

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from audit import audit
from core import db, now_iso, new_id, NO_ID

JWT_ALGORITHM = "HS256"
ACCESS_MINUTES = 30
REFRESH_DAYS = 7
MAX_ATTEMPTS = 5
MAX_USER_ATTEMPTS = 20  # per username across all IPs: backstop against distributed or spoofed-IP guessing
LOCKOUT_MINUTES = 15
USER_PUBLIC = {"_id": 0, "password_hash": 0, "mfa_secret": 0, "token_version": 0}
USER_AUTH = {"_id": 0, "password_hash": 0, "mfa_secret": 0}  # keeps token_version for session checks (never returned)

router = APIRouter(prefix="/auth", tags=["auth"])


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


# Checked against when the username doesn't exist, so a missing user takes as long as a wrong password.
_DUMMY_HASH = bcrypt.hashpw(b"timing-equaliser", bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def _secret() -> str:
    return os.environ["JWT_SECRET"]


def _token(user_id: str, kind: str, delta: timedelta, version: int = 0) -> str:
    # tv = the user's token_version when issued; jti lets a single token be revoked (logout).
    payload = {"sub": user_id, "type": kind, "tv": version, "jti": new_id(),
               "exp": datetime.now(timezone.utc) + delta}
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def _cookie_secure(request: Request) -> bool:
    """COOKIE_SECURE: "true"/"false" force the flag; "auto" (default in compose) marks cookies Secure only when
    the request itself was HTTPS (nginx reports that only for requests arriving through the trusted tunnel)."""
    mode = os.environ.get("COOKIE_SECURE", "true").lower()
    if mode == "auto":
        return request.url.scheme == "https"
    return mode == "true"


def set_auth_cookies(response: Response, user: dict, request: Request):
    """`user` needs id and (optionally) token_version. Bumping a user's token_version signs out all their sessions."""
    uid, version = user["id"], user.get("token_version", 0)
    opts = dict(httponly=True, secure=_cookie_secure(request), samesite="lax", path="/")
    response.set_cookie("access_token", _token(uid, "access", timedelta(minutes=ACCESS_MINUTES), version),
                        max_age=ACCESS_MINUTES * 60, **opts)
    response.set_cookie("refresh_token", _token(uid, "refresh", timedelta(days=REFRESH_DAYS), version),
                        max_age=REFRESH_DAYS * 86400, **opts)


def _claims(token: str, kind: str) -> dict:
    try:
        payload = jwt.decode(token, _secret(), algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    if payload.get("type") != kind:
        raise HTTPException(status_code=401, detail="Invalid token type")
    return payload


async def _user_for_token(token: str, kind: str) -> dict:
    """Validate a token against revocations and the user's current token_version. Returns the user incl. token_version."""
    payload = _claims(token, kind)
    jti = payload.get("jti")
    if jti and await db.revoked_tokens.find_one({"jti": jti}, NO_ID):
        raise HTTPException(status_code=401, detail="Session ended")
    user = await db.users.find_one({"id": payload["sub"]}, USER_AUTH)
    if not user or not user.get("active", True):
        raise HTTPException(status_code=401, detail="User not found or inactive")
    if payload.get("tv", 0) != user.get("token_version", 0):  # tokens from before the password/status change
        raise HTTPException(status_code=401, detail="Session expired, please sign in again")
    return user


async def _revoke(token: Optional[str]):
    """Deny-list one token until it would have expired anyway (TTL index cleans it up)."""
    if not token:
        return
    try:
        payload = jwt.decode(token, _secret(), algorithms=[JWT_ALGORITHM], options={"verify_exp": False})
    except jwt.InvalidTokenError:
        return
    jti, exp = payload.get("jti"), payload.get("exp")
    if jti and exp:
        await db.revoked_tokens.update_one({"jti": jti}, {"$set": {
            "jti": jti, "expires_at": datetime.fromtimestamp(exp, tz=timezone.utc)}}, upsert=True)


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        header = request.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            token = header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = await _user_for_token(token, "access")
    user.pop("token_version", None)
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
    update = {"identifier": identifier, "count": count, "updated_at": now_iso(), "at": datetime.now(timezone.utc)}
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
        await audit(request, "login_locked", target=username)
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 15 minutes.")

    user = await db.users.find_one({"username": username}, {"_id": 0})
    password_ok = verify_password(body.password, user["password_hash"] if user else _DUMMY_HASH)
    if not user or not user.get("active", True) or not password_ok:
        await audit(request, "login_failed", target=username)
        await _record_failure(identifier, MAX_ATTEMPTS)
        await _record_failure(user_identifier, MAX_USER_ATTEMPTS)
        raise HTTPException(status_code=401, detail="Invalid username or password")

    await db.login_attempts.delete_many({"identifier": {"$in": [identifier, user_identifier]}})
    # MFA hook: when user["mfa_enabled"] is true, a TOTP challenge step will be inserted here (Phase 2).
    await db.users.update_one({"id": user["id"]}, {"$set": {"last_login_at": now_iso()}})
    set_auth_cookies(response, user, request)
    await audit(request, "login", actor=user)
    return await db.users.find_one({"id": user["id"]}, USER_PUBLIC)


@router.post("/refresh")
async def refresh(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    user = await _user_for_token(token, "refresh")
    set_auth_cookies(response, user, request)
    user.pop("token_version", None)
    return user


@router.post("/logout")
async def logout(request: Request, response: Response):
    header = request.headers.get("Authorization", "")
    who = None
    for t in (request.cookies.get("access_token"), request.cookies.get("refresh_token"),
              header[7:] if header.startswith("Bearer ") else None):
        await _revoke(t)
        if t and who is None:
            try:
                who = await db.users.find_one({"id": jwt.decode(t, _secret(), algorithms=[JWT_ALGORITHM])["sub"]}, {"_id": 0, "id": 1, "username": 1})
            except Exception:  # noqa: BLE001
                pass
    if who:
        await audit(request, "logout", actor=who)
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"ok": True}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@router.post("/change-password")
async def change_password(body: ChangePasswordIn, request: Request, response: Response,
                          user: dict = Depends(get_current_user)):
    full = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    if not verify_password(body.current_password, full["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    # Bumping token_version signs out every other session (and any stolen token); keep this one signed in.
    await db.users.update_one({"id": user["id"]}, {"$set": {"password_hash": hash_password(body.new_password)},
                                                   "$inc": {"token_version": 1}})
    set_auth_cookies(response, await db.users.find_one({"id": user["id"]}, {"_id": 0, "id": 1, "token_version": 1}), request)
    await audit(request, "password_changed", actor=user)
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
        "mfa_enabled": False, "mfa_secret": None, "token_version": 0, "created_at": now_iso(), "last_login_at": None,
    }


@users_router.get("")
async def list_users(_: dict = Depends(require_admin)):
    return await db.users.find({}, USER_PUBLIC).sort("created_at", 1).to_list(500)


@users_router.post("")
async def create_user(body: UserCreate, request: Request, admin: dict = Depends(require_admin)):
    if await db.users.find_one({"username": body.username.strip().lower()}):
        raise HTTPException(status_code=400, detail="Username already exists")
    doc = user_doc(body.username, body.name, body.password, body.role)
    await db.users.insert_one(doc)
    await audit(request, "user_created", actor=admin, target=doc["username"], role=doc["role"])
    return await db.users.find_one({"id": doc["id"]}, USER_PUBLIC)


@users_router.patch("/{user_id}")
async def update_user(user_id: str, body: UserUpdate, request: Request, admin: dict = Depends(require_admin)):
    changes = body.model_dump(exclude_none=True)
    if user_id == admin["id"] and (changes.get("active") is False or changes.get("role") == "producer"):
        raise HTTPException(status_code=400, detail="You cannot deactivate or demote your own account")
    if changes:
        update = {"$set": changes}
        if changes.get("active") is False:
            update["$inc"] = {"token_version": 1}  # deactivation also kills any tokens that are still outstanding
        await db.users.update_one({"id": user_id}, update)
    user = await db.users.find_one({"id": user_id}, USER_PUBLIC)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if changes:
        await audit(request, "user_updated", actor=admin, target=user["username"], changes=changes)
    return user


@users_router.post("/{user_id}/reset-password")
async def reset_password(user_id: str, body: ResetPasswordIn, request: Request, admin: dict = Depends(require_admin)):
    res = await db.users.update_one({"id": user_id}, {"$set": {"password_hash": hash_password(body.new_password)},
                                                      "$inc": {"token_version": 1}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    await audit(request, "password_reset", actor=admin, target=user_id)
    return {"ok": True}


@users_router.delete("/{user_id}")
async def delete_user(user_id: str, request: Request, admin: dict = Depends(require_admin)):
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    user = await db.users.find_one({"id": user_id}, USER_PUBLIC)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user["role"] == "admin" and await db.users.count_documents({"role": "admin", "active": True, "id": {"$ne": user_id}}) == 0:
        raise HTTPException(status_code=400, detail="At least one active admin must remain")
    await db.users.delete_one({"id": user_id})
    await audit(request, "user_deleted", actor=admin, target=user["username"])
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
            "password_hash": hash_password(password), "active": True, "role": "admin"},
            "$inc": {"token_version": 1}})
