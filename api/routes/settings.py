"""Settings UI backend — Zerodha api_key/secret (api_secret is write-only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import KiteCredsIn
from core.config import get_settings
from core.schemas import ApiResponse
from core.security import current_user, require_csrf
from db.base import get_session
from services import settings_service

router = APIRouter(tags=["settings"])


@router.get("")
async def read(
    session: AsyncSession = Depends(get_session),
    user: str = Depends(current_user),
) -> ApiResponse:
    api_key = await settings_service.get(session, "kite_api_key")
    has_secret = bool(await settings_service.get(session, "kite_api_secret"))
    s = get_settings()
    return ApiResponse(
        data={
            "kite_api_key": api_key or "",
            "kite_api_secret_set": has_secret,
            "redirect_url": f"{s.base_url}/api/kite/callback",
            "postback_url": f"{s.base_url}/api/kite/postback",
        }
    )


@router.put("")
async def update(
    body: KiteCredsIn,
    session: AsyncSession = Depends(get_session),
    user: str = Depends(current_user),
    _: None = Depends(require_csrf),
) -> ApiResponse:
    await settings_service.set(session, "kite_api_key", body.api_key)
    if body.api_secret:  # only overwrite the secret when a non-empty value is sent
        await settings_service.set(session, "kite_api_secret", body.api_secret)
    await session.commit()
    return ApiResponse(data={"saved": True})
