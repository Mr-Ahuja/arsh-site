"""Repository for the tick archive (backtest replay dataset)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from db.models import Tick
from db.repository import BaseRepository


class TickRepository(BaseRepository[Tick]):
    model = Tick

    async def range(
        self,
        instrument_token: int,
        from_ts: datetime,
        to_ts: datetime,
    ) -> list[Tick]:
        """Ticks for one instrument between two UTC timestamps, ordered by time.
        Primary data source for tick-replay backtest mode."""
        stmt = (
            select(Tick)
            .where(
                Tick.instrument_token == instrument_token,
                Tick.ts >= from_ts,
                Tick.ts <= to_ts,
            )
            .order_by(Tick.ts)
        )
        result = await self.s.execute(stmt)
        return list(result.scalars().all())

    async def latest(self, instrument_token: int) -> Tick | None:
        """Most recently recorded tick for an instrument."""
        stmt = (
            select(Tick)
            .where(Tick.instrument_token == instrument_token)
            .order_by(Tick.ts.desc())
            .limit(1)
        )
        result = await self.s.execute(stmt)
        return result.scalar_one_or_none()
