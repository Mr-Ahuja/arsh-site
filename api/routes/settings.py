"""Settings UI backend — Zerodha credentials + Telegram config."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import KiteCredsIn, TelegramIn
from core.config import get_settings
from core.errors import ValidationError as AppValidationError
from core.schemas import ApiResponse
from core.security import current_user, require_csrf
from db.base import get_session
from integrations.telegram.notifier import send_message
from services import settings_service

router = APIRouter(tags=["settings"])


@router.get("")
async def read(
    session: AsyncSession = Depends(get_session),
    user: str = Depends(current_user),
) -> ApiResponse:
    api_key = await settings_service.get(session, "kite_api_key")
    has_kite_secret = bool(await settings_service.get(session, "kite_api_secret"))
    has_tg_token = bool(await settings_service.get(session, "telegram_bot_token"))
    chat_id = await settings_service.get(session, "telegram_chat_id")
    s = get_settings()
    return ApiResponse(
        data={
            "kite_api_key": api_key or "",
            "kite_api_secret_set": has_kite_secret,
            "redirect_url": f"{s.base_url}/api/kite/callback",
            "postback_url": f"{s.base_url}/api/kite/postback",
            "telegram_bot_token_set": has_tg_token,
            "telegram_chat_id": chat_id or "",
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
    if body.api_secret:
        await settings_service.set(session, "kite_api_secret", body.api_secret)
    await session.commit()
    return ApiResponse(data={"saved": True})


@router.put("/telegram")
async def update_telegram(
    body: TelegramIn,
    session: AsyncSession = Depends(get_session),
    user: str = Depends(current_user),
    _: None = Depends(require_csrf),
) -> ApiResponse:
    if body.bot_token:
        await settings_service.set(session, "telegram_bot_token", body.bot_token)
    if body.chat_id is not None:
        await settings_service.set(session, "telegram_chat_id", body.chat_id)
    await session.commit()
    return ApiResponse(data={"saved": True})


@router.post("/telegram/test")
async def test_telegram(
    session: AsyncSession = Depends(get_session),
    user: str = Depends(current_user),
    _: None = Depends(require_csrf),
) -> ApiResponse:
    bot_token = await settings_service.get(session, "telegram_bot_token")
    chat_id = await settings_service.get(session, "telegram_chat_id")
    if not bot_token or not chat_id:
        raise AppValidationError("Telegram bot token and chat ID must be configured first.")
    await send_message(bot_token, chat_id, "Test message from Trade Engine — configuration is working.")
    return ApiResponse(data={"sent": True})
