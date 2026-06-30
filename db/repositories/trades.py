"""Repository for Trade rows."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from db.models import Trade
from db.repository import BaseRepository


class TradeRepository(BaseRepository[Trade]):
    model = Trade

    async def open_trades(self, run_id: int) -> list[Trade]:
        """All open trades for a given run."""
        stmt = (
            select(Trade)
            .where(Trade.run_id == run_id, Trade.status == "open")
            .order_by(Trade.entry_at)
        )
        result = await self.s.execute(stmt)
        return list(result.scalars().all())

    async def count_today(self, run_id: int, date_str: str) -> int:
        """Count closed+open trades entered on a given date (YYYY-MM-DD, IST) for a run.
        Used by the max_trades_per_day risk guard."""
        stmt = select(func.count()).where(
            Trade.run_id == run_id,
            func.strftime("%Y-%m-%d", Trade.entry_at) == date_str,
            Trade.status != "cancelled",
        )
        result = await self.s.execute(stmt)
        return result.scalar_one()

    async def by_run(self, run_id: int, *, page: int = 1, size: int = 50) -> list[Trade]:
        return await self.list(
            where=Trade.run_id == run_id,
            order=Trade.entry_at.desc(),
            page=page,
            size=size,
        )

    async def close(
        self,
        id_: int,
        *,
        exit_price: float,
        exit_at: datetime,
        pnl: float,
        exit_reason: str,
    ) -> Trade | None:
        return await self.update(
            id_,
            exit_price=exit_price,
            exit_at=exit_at,
            pnl=pnl,
            status="closed",
            exit_reason=exit_reason,
        )
