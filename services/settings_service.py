"""Encrypted key-value accessor (reused by routes + kite credentials)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.crypto import decrypt, encrypt
from db.models import Setting


async def get(session: AsyncSession, key: str) -> str | None:
    row = await session.get(Setting, key)
    if row is None:
        return None
    return decrypt(row.value_enc, get_settings().app_secret)


async def set(session: AsyncSession, key: str, value: str) -> None:
    value_enc = encrypt(value, get_settings().app_secret)
    now = datetime.now(UTC)
    row = await session.get(Setting, key)
    if row is None:
        session.add(Setting(key=key, value_enc=value_enc, updated_at=now))
    else:
        row.value_enc = value_enc
        row.updated_at = now
    await session.flush()


async def all_keys(session: AsyncSession) -> list[str]:
    result = await session.execute(select(Setting.key))
    return list(result.scalars().all())
