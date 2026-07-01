"""Kite Historical Data API — fetch OHLC candles for backtesting."""

from __future__ import annotations

import asyncio
from datetime import date, datetime

from integrations.kite.client import get_kite


async def resolve_token(symbol: str) -> int:
    """Resolve a user-entered instrument to a Kite integer instrument_token.

    Accepts:
      - a numeric token            → "256265"        → 256265
      - EXCHANGE:token             → "NSE:256265"    → 256265
      - EXCHANGE:tradingsymbol     → "NSE:KOTAKBANK" → resolved via Kite
      - a bare tradingsymbol       → "KOTAKBANK"     → resolved as NSE:KOTAKBANK

    The Kite historical API only accepts integer tokens, so a symbol name must be
    looked up. Requires a connected client (ensure it before calling).
    """
    s = symbol.strip()
    if s.isdigit():
        return int(s)

    if ":" in s:
        exchange, name = s.split(":", 1)
        if name.isdigit():
            return int(name)
        key = f"{exchange.upper()}:{name.upper()}"
    else:
        key = f"NSE:{s.upper()}"

    client = get_kite()
    if not client.connected:
        raise RuntimeError("Kite not connected — log in via the dashboard first.")

    quote = await asyncio.to_thread(client.kite.ltp, [key])
    if not quote or key not in quote:
        raise RuntimeError(
            f"Could not find instrument {symbol!r}. Use a numeric token, or a valid "
            f"symbol like 'NSE:KOTAKBANK' (defaults to NSE if no exchange given)."
        )
    return int(quote[key]["instrument_token"])


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
