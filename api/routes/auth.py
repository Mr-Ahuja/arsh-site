"""App authentication: login (static single user), me, logout."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Response

from api.schemas import LoginIn
from core.config import get_settings
from core.errors import AuthError
from core.schemas import ApiResponse
from core.security import current_user, issue_jwt, require_csrf, verify_password
from services import throttle

router = APIRouter(tags=["auth"])

_COOKIE_TTL = 8 * 3600


@router.post("/login")
def login(body: LoginIn, response: Response) -> ApiResponse:
    s = get_settings()
    throttle.check(body.username)
    if body.username != s.app_username or not verify_password(s.app_password_hash, body.password):
        throttle.fail(body.username)
        raise AuthError("invalid credentials")
    throttle.reset(body.username)

    token = issue_jwt(body.username, s.app_secret, ttl_s=_COOKIE_TTL)
    secure = s.cookie_secure
    response.set_cookie(
        "session", token, httponly=True, secure=secure, samesite="strict", max_age=_COOKIE_TTL
    )
    response.set_cookie(
        "csrf",
        secrets.token_urlsafe(16),
        httponly=False,
        secure=secure,
        samesite="strict",
        max_age=_COOKIE_TTL,
    )
    return ApiResponse(data={"username": body.username})


@router.get("/me")
def me(user: str = Depends(current_user)) -> ApiResponse:
    return ApiResponse(data={"username": user})


@router.post("/logout")
def logout(response: Response, _: None = Depends(require_csrf)) -> ApiResponse:
    response.delete_cookie("session")
    response.delete_cookie("csrf")
    return ApiResponse()
