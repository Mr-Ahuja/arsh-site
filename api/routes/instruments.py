"""Instruments API — searchable, DB-buffered NSE/BSE equity list for the picker."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.schemas import ApiResponse
from core.security import current_user, require_csrf
from db.base import get_session
from services import instrument_service

router = APIRouter(tags=["instruments"])


@router.get("/status")
async def instruments_status(
    user: str = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    return ApiResponse(data=await instrument_service.status(session))


@router.get("/search")
async def instruments_search(
    q: str = "",
    exchange: str | None = None,
    limit: int = 30,
    user: str = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    # First use: lazily populate the buffer from Kite so the picker isn't empty.
    await instrument_service.ensure_loaded(session)
    results = await instrument_service.search(session, q=q, exchange=exchange, limit=limit)
    return ApiResponse(data={"results": results})


@router.post("/refresh")
async def instruments_refresh(
    user: str = Depends(current_user),
    _csrf: None = Depends(require_csrf),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    return ApiResponse(data=await instrument_service.refresh(session))
