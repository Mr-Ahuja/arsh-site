"""Auth primitives reused everywhere: password hashing, JWT, current_user dep, CSRF."""

from __future__ import annotations

import time

import jwt
from argon2 import PasswordHasher
from fastapi import Request

from core.config import get_settings
from core.errors import AuthError, ForbiddenError

ph = PasswordHasher()


def verify_password(hash_: str, pw: str) -> bool:
    try:
        return ph.verify(hash_, pw)
    except Exception:
        return False


def issue_jwt(sub: str, secret: str, ttl_s: int = 8 * 3600) -> str:
    now = int(time.time())
    return jwt.encode({"sub": sub, "iat": now, "exp": now + ttl_s}, secret, algorithm="HS256")


def current_user(request: Request) -> str:
    token = request.cookies.get("session")
    if not token:
        raise AuthError("not authenticated")
    try:
        payload = jwt.decode(token, get_settings().app_secret, algorithms=["HS256"])
        return str(payload["sub"])
    except jwt.PyJWTError as exc:
        raise AuthError("invalid session") from exc


def decode_token(token: str) -> dict:
    """Decode and validate a JWT. Used by the WebSocket endpoint (no cookie available)."""
    return jwt.decode(token, get_settings().app_secret, algorithms=["HS256"])


def require_csrf(request: Request) -> None:
    cookie = request.cookies.get("csrf")
    header = request.headers.get("x-csrf-token")
    if not cookie or cookie != header:
        raise ForbiddenError("csrf failed")
