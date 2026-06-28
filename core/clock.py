"""IST time + market-session helpers (single source of truth for time)."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))

MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)


def now_ist() -> datetime:
    return datetime.now(IST)


def today_ist() -> str:
    """Today's date in IST as YYYY-MM-DD (the Kite token's validity day)."""
    return now_ist().strftime("%Y-%m-%d")


def is_market_hours(dt: datetime | None = None) -> bool:
    dt = dt or now_ist()
    if dt.weekday() >= 5:  # Sat/Sun
        return False
    return MARKET_OPEN <= dt.timetz().replace(tzinfo=None) <= MARKET_CLOSE
