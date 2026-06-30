"""Health endpoint — liveness + Kite connectivity + env."""

from __future__ import annotations

from fastapi import APIRouter

from core.config import get_settings
from core.schemas import ApiResponse
from integrations.kite.client import get_kite

router = APIRouter(tags=["health"])


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
