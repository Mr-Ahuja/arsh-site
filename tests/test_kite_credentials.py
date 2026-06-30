import pytest

from core.errors import KiteError
from db.base import async_session
from integrations.kite.credentials import get_kite_credentials
from services import settings_service


@pytest.mark.asyncio
async def test_prefers_db_over_env(monkeypatch):
    from core import config

    monkeypatch.setattr(config.get_settings(), "kite_api_key", "env_key", raising=False)
    monkeypatch.setattr(config.get_settings(), "kite_api_secret", "env_secret", raising=False)

    async with async_session() as session:
        await settings_service.set(session, "kite_api_key", "db_key")
        await settings_service.set(session, "kite_api_secret", "db_secret")
        await session.commit()
        key, secret = await get_kite_credentials(session)
    assert key == "db_key"
    assert secret == "db_secret"


@pytest.mark.asyncio
async def test_falls_back_to_env(monkeypatch):
    from core import config

    monkeypatch.setattr(config.get_settings(), "kite_api_key", "env_key", raising=False)
    monkeypatch.setattr(config.get_settings(), "kite_api_secret", "env_secret", raising=False)

    async with async_session() as session:
        key, secret = await get_kite_credentials(session)
    assert key == "env_key"
    assert secret == "env_secret"


@pytest.mark.asyncio
async def test_raises_when_neither_set(monkeypatch):
    from core import config

    monkeypatch.setattr(config.get_settings(), "kite_api_key", "", raising=False)
    monkeypatch.setattr(config.get_settings(), "kite_api_secret", "", raising=False)

    async with async_session() as session:
        with pytest.raises(KiteError):
            await get_kite_credentials(session)
