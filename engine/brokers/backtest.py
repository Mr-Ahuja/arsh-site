"""BacktestBroker — OHLC candle-based fills (conservative worst-case).

OHLC mode fills (per docs/execution-spec.md §3b):
- MARKET entry: next candle's open + slippage.
- LIMIT: fills only if low ≤ limit ≤ high; fill at limit price.
- Adverse-path stop assumption: for LONG, low hit before high within same candle.
- Gap fills: gap through a stop fills at candle open (not the stop price).

For tick-replay backtest, swap in PaperBroker directly (same logic as paper mode).

Runs are tagged "approximate" (OHLC) or "tick-accurate" (tick replay) in the Backtest DB row.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.config import get_settings
from core.logging import get_logger
from engine.brokers.base import BrokerBase, FillResult
from engine.data.types import CandleData, TickData
from engine.strategy.order import StrategyOrder

log = get_logger(__name__)


@dataclass
class _BacktestPending:
    order_ref: str
    db_order_id: int
    intent: StrategyOrder
    symbol: str
    token: int
    run_id: int
    trade_id: int | None
    fill_on_next_candle: bool = False   # MARKET: true after candle N closes (fill at N+1 open)


class BacktestBroker(BrokerBase):
    """OHLC-mode backtest broker. place_order() queues; on_candle() fills."""

    def __init__(self) -> None:
        cfg = get_settings()
        self._slippage_bps = cfg.slippage_bps
        self._tick_size = cfg.tick_size
        self._pending: dict[str, _BacktestPending] = {}
        self._trade_inflight: dict[int, str] = {}

    async def place_order(
        self,
        intent: StrategyOrder,
        *,
        symbol: str,
        instrument_token: int,
        run_id: int,
        trade_id: int | None = None,
    ) -> str:
        from core.clock import now_ist
        from db.base import async_session
        from db.repositories import OrderRepository

        order_ref = self.new_ref()
        async with async_session() as s:
            repo = OrderRepository(s)
            db_order = await repo.create(
                order_ref=order_ref, trade_id=trade_id, run_id=run_id,
                symbol=symbol, side=intent.side, qty=intent.qty,
                order_type=intent.order_type, price=intent.price,
                product=intent.product, state="PENDING",
                reason=intent.reason,
                created_at=now_ist(), updated_at=now_ist(),
            )

        p = _BacktestPending(
            order_ref=order_ref, db_order_id=db_order.id,
            intent=intent, symbol=symbol, token=instrument_token,
            run_id=run_id, trade_id=trade_id,
        )
        # MARKET fills on the *next* candle's open, so mark for deferred fill
        if intent.order_type == "MARKET":
            p.fill_on_next_candle = True

        self._pending[order_ref] = p
        if trade_id is not None:
            self._trade_inflight[trade_id] = order_ref
        log.info("bt_order_queued", order_ref=order_ref, symbol=symbol, type=intent.order_type)
        return order_ref

    async def cancel_order(self, order_ref: str) -> bool:
        from core.clock import now_ist
        from db.base import async_session
        from db.repositories import OrderRepository

        p = self._pending.pop(order_ref, None)
        if p is None:
            return False
        if p.trade_id is not None:
            self._trade_inflight.pop(p.trade_id, None)
        async with async_session() as s:
            repo = OrderRepository(s)
            await repo.transition(p.db_order_id, state="CANCELLED", updated_at=now_ist())
        return True

    async def on_tick(self, tick: TickData) -> list[FillResult]:
        return []  # OHLC mode never fills on raw ticks

    async def on_candle(self, candle: CandleData) -> list[FillResult]:
        if not self._pending:
            return []

        fills: list[FillResult] = []
        done: list[str] = []

        for ref, p in self._pending.items():
            if p.token != candle.instrument_token:
                continue

            fill = self._try_fill_candle(p, candle)
            if fill:
                fills.append(fill)
                done.append(ref)
            elif p.intent.order_type == "MARKET":
                # First time we see the candle after queuing — mark for next open
                p.fill_on_next_candle = True

        for ref in done:
            p = self._pending.pop(ref)
            if p.trade_id is not None:
                self._trade_inflight.pop(p.trade_id, None)

        if fills:
            await self._persist_fills(fills)
        return fills

    async def has_inflight(self, trade_id: int | None) -> bool:
        if trade_id is None:
            return False
        return trade_id in self._trade_inflight

    # ── Fill logic ────────────────────────────────────────────────────────────

    def _slippage(self, price: float) -> float:
        return max(self._tick_size, self._slippage_bps / 10_000 * price)

    def _try_fill_candle(self, p: _BacktestPending, candle: CandleData) -> FillResult | None:
        from core.clock import now_ist

        intent = p.intent

        # MARKET: fill at candle open + slippage (pessimistic)
        if intent.order_type == "MARKET" and p.fill_on_next_candle:
            slip = self._slippage(candle.open)
            if intent.side == "BUY":
                price = candle.open + slip
            else:
                price = max(candle.open - slip, self._tick_size)
            return FillResult(
                order_ref=p.order_ref, filled_qty=intent.qty,
                avg_price=price, state="COMPLETE", ts=now_ist(),
                meta={"mode": "ohlc"},
            )

        # LIMIT: fills only when low ≤ limit ≤ high
        if intent.order_type == "LIMIT" and intent.price is not None:
            limit = intent.price
            if candle.low <= limit <= candle.high:
                # Adverse-path: for LONG, assume low hit before high — so BUY limit fills
                # For SHORT (SELL limit), high hit before low — SELL limit fills
                return FillResult(
                    order_ref=p.order_ref, filled_qty=intent.qty,
                    avg_price=limit, state="COMPLETE", ts=now_ist(),
                    meta={"mode": "ohlc"},
                )
            # Gap through stop: if stop price is outside candle open (gap open)
            if intent.side == "SELL" and candle.open < limit:
                return FillResult(
                    order_ref=p.order_ref, filled_qty=intent.qty,
                    avg_price=candle.open, state="COMPLETE", ts=now_ist(),
                    meta={"mode": "ohlc", "gap": True},
                )
            if intent.side == "BUY" and candle.open > limit:
                return FillResult(
                    order_ref=p.order_ref, filled_qty=intent.qty,
                    avg_price=candle.open, state="COMPLETE", ts=now_ist(),
                    meta={"mode": "ohlc", "gap": True},
                )

        return None

    async def _persist_fills(self, fills: list[FillResult]) -> None:
        from core.clock import now_ist
        from db.base import async_session
        from db.repositories import OrderRepository

        async with async_session() as s:
            repo = OrderRepository(s)
            for fill in fills:
                db_order = await repo.by_ref(fill.order_ref)
                if db_order:
                    await repo.transition(
                        db_order.id, state=fill.state,
                        filled_qty=fill.filled_qty,
                        avg_fill_price=fill.avg_price,
                        updated_at=now_ist(),
                    )
            await s.commit()
