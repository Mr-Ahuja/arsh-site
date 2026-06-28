"""Kite session business logic — store the day's token (encrypted) and report status.

Shared by the API routes now and the engine later.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.clock import today_ist
from core.config import get_settings
from core.crypto import decrypt, encrypt
from db.models import KiteSession
from integrations.kite.client import get_kite
from integrations.kite.credentials import get_kite_credentials


async def _latest_session(session: AsyncSession) -> KiteSession | None:
    stmt = select(KiteSession).order_by(KiteSession.id.desc()).limit(1)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def store_session(session: AsyncSession, data: dict[str, Any]) -> KiteSession:
    """Encrypt + persist today's access token and set it on the shared client."""
    secret = get_settings().app_secret
    access_token = data["access_token"]
    row = KiteSession(
        user_id=str(data.get("user_id", "")),
        access_token_enc=encrypt(access_token, secret),
        valid_for_date=today_ist(),
        created_at=datetime.now(UTC),
    )
    session.add(row)
    await session.flush()

    # Configure the shared client so subsequent API calls are authenticated.
    api_key, _ = await get_kite_credentials(session)
    client = get_kite()
    client.configure(api_key)
    client.set_access_token(access_token)
    return row


async def status(session: AsyncSession) -> dict[str, Any]:
    row = await _latest_session(session)
    connected = bool(row and row.valid_for_date == today_ist())
    return {
        "connected": connected,
        "user_id": row.user_id if row else None,
        "valid_for_date": row.valid_for_date if row else None,
    }


async def restore_client(session: AsyncSession) -> bool:
    """On startup, re-arm the shared client from today's stored token (if any)."""
    row = await _latest_session(session)
    if not row or row.valid_for_date != today_ist():
        return False
    try:
        api_key, _ = await get_kite_credentials(session)
    except Exception:
        return False
    access_token = decrypt(row.access_token_enc, get_settings().app_secret)
    client = get_kite()
    client.configure(api_key)
    client.set_access_token(access_token)
    return True
