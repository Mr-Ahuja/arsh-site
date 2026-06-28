"""Single source of truth for the Kite api_key/secret — DB-first with .env bootstrap fallback.

Both the in-app Settings UI (DB, encrypted) and the .env work; DB takes precedence.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.errors import KiteError
from services import settings_service


async def get_kite_credentials(session: AsyncSession) -> tuple[str, str]:
    s = get_settings()
    api_key = (await settings_service.get(session, "kite_api_key")) or s.kite_api_key
    api_secret = (await settings_service.get(session, "kite_api_secret")) or s.kite_api_secret
    if not api_key or not api_secret:
        raise KiteError("Kite API key/secret not configured — set them in Settings")
    return api_key, api_secret
