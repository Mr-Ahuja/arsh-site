"""Health endpoint — liveness, Kite connectivity, settings readiness."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.schemas import ApiResponse
from core.security import current_user
from db.base import get_session
from db.models import Setting
from integrations.kite.client import get_kite

router = APIRouter(tags=["health"])

_REQUIRED_SETTINGS = {"kite_api_key", "kite_api_secret"}
_OPTIONAL_SETTINGS = {"telegram_bot_token", "telegram_chat_id"}


@router.get("/health")
def health() -> ApiResponse:
    s = get_settings()
    return ApiResponse(
        data={
            "status": "ok",
            "kite_connected": get_kite().connected,
            "env": s.app_env,
        }
    )


@router.get("/health/system")
async def system_health(
    user: str = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    """Detailed health for the Settings/System panel."""
    cfg = get_settings()
    kite = get_kite()

    # Check which required settings are present in DB
    result = await session.execute(
        select(Setting.key, func.length(Setting.value_enc).label("set"))
    )
    present: set[str] = {row.key for row in result if row.set > 0}
    missing = _REQUIRED_SETTINGS - present
    optional_set = _OPTIONAL_SETTINGS & present

    # DB file size
    db_size_bytes: int | None = None
    try:
        db_size_bytes = os.path.getsize(cfg.db_path)
    except OSError:
        pass

    return ApiResponse(data={
        "kite_connected": kite.connected,
        "required_settings_ok": len(missing) == 0,
        "missing_settings": sorted(missing),
        "optional_configured": sorted(optional_set),
        "db_size_bytes": db_size_bytes,
        "env": cfg.app_env,
    })
