"""Kite OAuth endpoints: login-url, callback, status, postback stub."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import KiteError
from core.logging import get_logger
from core.schemas import ApiResponse
from core.security import current_user
from db.base import get_session
from integrations.kite.auth import exchange, login_url
from services import kite_service

router = APIRouter(tags=["kite"])
log = get_logger(__name__)


@router.get("/login-url")
async def kite_login_url(
    session: AsyncSession = Depends(get_session),
    user: str = Depends(current_user),
) -> ApiResponse:
    return ApiResponse(data={"url": await login_url(session)})


@router.get("/callback")
async def kite_callback(
    request_token: str,
    status: str = "success",
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    # Zerodha redirects the browser here: ?request_token=...&action=login&status=success
    if status != "success":
        raise KiteError("kite login failed")
    data = await exchange(session, request_token)
    await kite_service.store_session(session, data)
    await session.commit()
    return RedirectResponse(url="/?kite=connected", status_code=302)


@router.get("/status")
async def kite_status(
    session: AsyncSession = Depends(get_session),
    user: str = Depends(current_user),
) -> ApiResponse:
    return ApiResponse(data=await kite_service.status(session))


@router.post("/postback")
async def kite_postback(request: Request) -> dict:
    # Public endpoint; Kite order updates. Task 07 verifies the checksum + enqueues the update.
    payload = await request.json()
    log.info("kite_postback", payload=payload)
    return {"ok": True}
