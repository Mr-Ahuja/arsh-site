"""Async SQLite engine, session factory, get_session() dependency, and declarative Base."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from core.config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine():
    db_path = get_settings().db_path
    # Ensure the parent directory exists (e.g. ./data).
    parent = os.path.dirname(db_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    # NullPool: every operation opens its own short-lived connection. This avoids binding a
    # pooled aiosqlite connection to one event loop (WAL mode persists at the DB-file level,
    # so concurrent readers are still fine).
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        connect_args={"timeout": 5},
        poolclass=NullPool,
        future=True,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _set_pragma(dbapi_conn, _record):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    return engine


engine = _make_engine()
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session() as session:
        yield session
