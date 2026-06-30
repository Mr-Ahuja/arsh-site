"""Centralized FastAPI dependencies (re-exported for routes)."""

from __future__ import annotations

from core.config import Settings, get_settings
from core.security import current_user, require_csrf
from db.base import get_session

__all__ = ["get_session", "current_user", "require_csrf", "get_settings", "Settings"]
