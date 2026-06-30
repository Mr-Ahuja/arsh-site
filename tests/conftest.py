"""Shared test fixtures. Env is set BEFORE any project import so get_settings() picks it up."""

from __future__ import annotations

import os
import tempfile

# --- configure environment before importing the app/config (lru_cache) ---
_DB_FD, _DB_PATH = tempfile.mkstemp(suffix=".db")
os.close(_DB_FD)

_TEST_PASSWORD = "testpass123"

os.environ["APP_ENV"] = "dev"
os.environ["DB_PATH"] = _DB_PATH
os.environ["APP_SECRET"] = "test-secret-key-for-tests"
os.environ["APP_USERNAME"] = "mrahuja"
os.environ["BASE_URL"] = "http://127.0.0.1:8000"
os.environ["KITE_API_KEY"] = ""
os.environ["KITE_API_SECRET"] = ""

from argon2 import PasswordHasher  # noqa: E402

os.environ["APP_PASSWORD_HASH"] = PasswordHasher().hash(_TEST_PASSWORD)

import asyncio  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.app import create_app  # noqa: E402
from db.base import Base, engine  # noqa: E402
from services import throttle  # noqa: E402


def _run(coro):
    """Run a coroutine on a fresh event loop (engine uses NullPool, so no loop binding)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    async def _create():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    _run(_create())
    yield


@pytest.fixture(autouse=True)
def _clean_state():
    """Reset in-memory throttle and DB rows between tests."""
    throttle._state.clear()

    async def _wipe():
        from sqlalchemy import delete

        from db.models import Event, KiteSession, Setting

        async with engine.begin() as conn:
            for model in (Setting, KiteSession, Event):
                await conn.execute(delete(model))

    _run(_wipe())
    yield


@pytest.fixture
def password() -> str:
    return _TEST_PASSWORD


@pytest.fixture
def client():
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture
def auth_client(client, password):
    """A logged-in client with session + csrf cookies set."""
    resp = client.post("/api/auth/login", json={"username": "mrahuja", "password": password})
    assert resp.status_code == 200
    return client
