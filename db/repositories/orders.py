"""Repository for Order rows (full order state machine)."""

from __future__ import annotations

from sqlalchemy import select

from db.models import Order
from db.repository import BaseRepository

_INFLIGHT = ("PENDING", "OPEN", "PARTIAL")


class OrderRepository(BaseRepository[Order]):
    model = Order

    async def by_ref(self, order_ref: str) -> Order | None:
        """Look up by client-side UUID — the idempotency key."""
        stmt = select(Order).where(Order.order_ref == order_ref)
        result = await self.s.execute(stmt)
        return result.scalar_one_or_none()

    async def by_trade(self, trade_id: int) -> list[Order]:
        """All orders belonging to a trade, oldest first."""
        stmt = (
            select(Order)
            .where(Order.trade_id == trade_id)
            .order_by(Order.created_at)
        )
        result = await self.s.execute(stmt)
        return list(result.scalars().all())

    async def pending_for_trade(self, trade_id: int) -> list[Order]:
        """In-flight orders for a trade (PENDING / OPEN / PARTIAL).
        Used to prevent duplicate order submission."""
        stmt = select(Order).where(
            Order.trade_id == trade_id,
            Order.state.in_(_INFLIGHT),
        )
        result = await self.s.execute(stmt)
        return list(result.scalars().all())

    async def transition(self, id_: int, *, state: str, **kw: object) -> Order | None:
        """Update order state + any fill fields atomically."""
        return await self.update(id_, state=state, **kw)
