"""Kite Historical Data API — fetch OHLC candles for backtesting."""

from __future__ import annotations

import asyncio
from datetime import date, datetime

from integrations.kite.client import get_kite


async def fetch_candles(
    instrument_token: int,
    from_date: date | str,
    to_date: date | str,
    interval: str,
) -> list[dict]:
    """Fetch OHLC candles from Kite Historical API.

    interval: minute | 3minute | 5minute | 10minute | 15minute | 30minute |
              60minute | day
    Returns list of dicts: {date, open, high, low, close, volume}
    """
    client = get_kite()
    if not client.connected:
        raise RuntimeError("Kite not connected — log in via the dashboard first.")

    if isinstance(from_date, str):
        from_date = datetime.fromisoformat(from_date).date()
    if isinstance(to_date, str):
        to_date = datetime.fromisoformat(to_date).date()

    data = await asyncio.to_thread(
        client.kite.historical_data,
        instrument_token,
        from_date,
        to_date,
        interval,
        continuous=False,
        oi=False,
    )
    return data  # [{date, open, high, low, close, volume}, ...]
