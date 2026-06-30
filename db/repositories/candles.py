"""Repository for the OHLCV candle cache."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from db.models import Candle
from db.repository import BaseRepository


class CandleRepository(BaseRepository[Candle]):
    model = Candle

    async def range(
        self,
        instrument_token: int,
        timeframe: str,
        from_ts: datetime,
        to_ts: datetime,
    ) -> list[Candle]:
        """Candles for one instrument/timeframe between two UTC timestamps, ordered by time."""
        stmt = (
            select(Candle)
            .where(
                Candle.instrument_token == instrument_token,
                Candle.timeframe == timeframe,
                Candle.ts >= from_ts,
                Candle.ts <= to_ts,
            )
            .order_by(Candle.ts)
        )
        result = await self.s.execute(stmt)
        return list(result.scalars().all())

    async def upsert(
        self,
        *,
        instrument_token: int,
        timeframe: str,
        ts: datetime,
        open: float,
        high: float,
        low: float,
        close: float,
        volume: int,
        source: str,
    ) -> None:
        """Insert or update a candle (ON CONFLICT on the unique key)."""
        stmt = (
            sqlite_insert(Candle)
            .values(
                instrument_token=instrument_token,
                timeframe=timeframe,
                ts=ts,
                open=open,
                high=high,
                low=low,
                close=close,
                volume=volume,
                source=source,
            )
            .on_conflict_do_update(
                index_elements=["instrument_token", "timeframe", "ts"],
                set_=dict(
                    open=open,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                    source=source,
                ),
            )
        )
        await self.s.execute(stmt)
