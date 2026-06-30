"""Kite OAuth flow — login URL + request_token -> access_token exchange.

Credentials are resolved via credentials.py (DB-first). generate_session() computes the Kite
checksum SHA-256(api_key + request_token + api_secret) internally.
"""

from __future__ import annotations

from typing import Any

from kiteconnect import KiteConnect
from sqlalchemy.ext.asyncio import AsyncSession

from integrations.kite.credentials import get_kite_credentials


async def login_url(session: AsyncSession) -> str:
    api_key, _ = await get_kite_credentials(session)
    return KiteConnect(api_key=api_key).login_url()


async def exchange(session: AsyncSession, request_token: str) -> dict[str, Any]:
    api_key, api_secret = await get_kite_credentials(session)
    kite = KiteConnect(api_key=api_key)
    # data has: access_token, public_token, user_id, ...
    return kite.generate_session(request_token, api_secret=api_secret)
