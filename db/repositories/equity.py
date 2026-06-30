"""Repository for the equity / P&L time series."""

from __future__ import annotations

from sqlalchemy import select

from db.models import Equity
from db.repository import BaseRepository


class EquityRepository(BaseRepository[Equity]):
    model = Equity

    async def latest(self, run_id: int) -> Equity | None:
        """Most recent equity snapshot for a run."""
        stmt = (
            select(Equity)
            .where(Equity.run_id == run_id)
            .order_by(Equity.ts.desc())
            .limit(1)
        )
        result = await self.s.execute(stmt)
        return result.scalar_one_or_none()

    async def for_run(self, run_id: int) -> list[Equity]:
        """Full equity curve for a run, oldest first (for the chart)."""
        stmt = (
            select(Equity)
            .where(Equity.run_id == run_id)
            .order_by(Equity.ts)
        )
        result = await self.s.execute(stmt)
        return list(result.scalars().all())
