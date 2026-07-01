"""Instrument buffer — sync the Kite NSE/BSE equity list into the DB and search it.

The Backtest picker needs a searchable list of tradable instruments. Kite's
instruments dump is large and only changes daily, so we buffer it in the DB and
refresh once per day (wipe + reload). Searches then run against SQLite, not Kite.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import delete, func, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.clock import today_ist
from core.logging import get_logger
from db.models import Instrument
from integrations.kite.client import get_kite
from services import kite_service

log = get_logger(__name__)

_EXCHANGES = ("NSE", "BSE")
_EQUITY_TYPES = {"EQ"}

# Guards against two concurrent refreshes hammering Kite at once.
_refresh_lock = asyncio.Lock()


async def status(session: AsyncSession) -> dict:
    """How many instruments are buffered, and when they were last synced."""
    count = (await session.execute(select(func.count()).select_from(Instrument))).scalar_one()
    synced = (await session.execute(select(Instrument.synced_on).limit(1))).scalar_one_or_none()
    return {"count": int(count), "synced_on": synced}


def _fetch_all() -> list[dict]:
    """Blocking Kite calls — run inside asyncio.to_thread."""
    client = get_kite()
    rows: list[dict] = []
    for exchange in _EXCHANGES:
        try:
            rows.extend(client.kite.instruments(exchange))
        except Exception as exc:  # noqa: BLE001
            log.warning("instruments_fetch_error", exchange=exchange, error=str(exc))
    return rows


async def refresh(session: AsyncSession) -> dict:
    """Fetch NSE+BSE equities from Kite and replace the buffered list. Daily-idempotent."""
    async with _refresh_lock:
        if not await kite_service.ensure_client(session):
            raise RuntimeError("Kite not connected — log in via the dashboard first.")

        raw = await asyncio.to_thread(_fetch_all)
        today = today_ist()
        seen: set[tuple[str, str]] = set()
        records: list[dict] = []
        for inst in raw:
            if inst.get("instrument_type") not in _EQUITY_TYPES:
                continue
            exchange = inst.get("exchange", "")
            symbol = inst.get("tradingsymbol", "")
            if exchange not in _EXCHANGES or not symbol:
                continue
            key = (exchange, symbol)
            if key in seen:
                continue
            seen.add(key)
            records.append({
                "instrument_token": int(inst["instrument_token"]),
                "exchange": exchange,
                "tradingsymbol": symbol,
                "name": (inst.get("name") or "")[:128],
                "synced_on": today,
            })

        await session.execute(delete(Instrument))
        if records:
            await session.execute(insert(Instrument), records)
        await session.commit()
        log.info("instruments_refreshed", count=len(records), synced_on=today)
        return {"count": len(records), "synced_on": today}


async def ensure_loaded(session: AsyncSession) -> None:
    """Populate the buffer if it's empty (first use). Does not force a daily refresh."""
    count = (await session.execute(select(func.count()).select_from(Instrument))).scalar_one()
    if count == 0:
        await refresh(session)


async def search(
    session: AsyncSession,
    q: str,
    exchange: str | None = None,
    limit: int = 30,
) -> list[dict]:
    """Search buffered instruments by trading symbol or company name.

    Prefix matches on the trading symbol rank first, then other matches.
    """
    stmt = select(Instrument)
    if exchange in _EXCHANGES:
        stmt = stmt.where(Instrument.exchange == exchange)

    q = (q or "").strip()
    if q:
        like = f"%{q.upper()}%"
        prefix = f"{q.upper()}%"
        stmt = stmt.where(
            or_(
                func.upper(Instrument.tradingsymbol).like(like),
                func.upper(Instrument.name).like(like),
            )
        ).order_by(
            # symbol-prefix hits first, then alphabetical
            func.upper(Instrument.tradingsymbol).like(prefix).desc(),
            Instrument.tradingsymbol.asc(),
        )
    else:
        stmt = stmt.order_by(Instrument.tradingsymbol.asc())

    rows = (await session.execute(stmt.limit(max(1, min(limit, 100))))).scalars().all()
    return [
        {
            "instrument_token": r.instrument_token,
            "exchange": r.exchange,
            "tradingsymbol": r.tradingsymbol,
            "name": r.name,
            "label": f"{r.exchange}:{r.tradingsymbol}",
        }
        for r in rows
    ]
