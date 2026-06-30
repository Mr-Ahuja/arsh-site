"""Repository for TradeVar snapshots (pos.vars audit trail)."""

from __future__ import annotations

from sqlalchemy import select

from db.models import TradeVar
from db.repository import BaseRepository


class TradeVarRepository(BaseRepository[TradeVar]):
    model = TradeVar

    async def latest(self, trade_id: int) -> TradeVar | None:
        """Most recent pos.vars snapshot for a trade."""
        stmt = (
            select(TradeVar)
            .where(TradeVar.trade_id == trade_id)
            .order_by(TradeVar.ts.desc())
            .limit(1)
        )
        result = await self.s.execute(stmt)
        return result.scalar_one_or_none()

    async def for_trade(self, trade_id: int) -> list[TradeVar]:
        """Full audit trail for a trade, oldest first."""
        stmt = (
            select(TradeVar)
            .where(TradeVar.trade_id == trade_id)
            .order_by(TradeVar.ts)
        )
        result = await self.s.execute(stmt)
        return list(result.scalars().all())
