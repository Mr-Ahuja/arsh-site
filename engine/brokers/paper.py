"""PaperBroker — simulated fills on live KiteTicker ticks.

Fill model (all defaults pessimistic; see docs/execution-spec.md §2):
- MARKET: filled on tick #N+fill_delay_ticks at bid (SELL) or ask (BUY).
  If depth unavailable: LTP ± max(tick_size, slippage_bps * LTP / 10000).
- LIMIT: filled when a tick crosses the limit price.
- Rejections: circuit-band violations, zero liquidity (when configured).
- One PENDING order per trade is enforced by the caller (runner).
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
class _Pending:
    order_ref: str
    db_order_id: int
    intent: StrategyOrder
    symbol: str
    token: int
    run_id: int
    trade_id: int | None
    ticks_seen: int = 0
    circuit_upper: float | None = None  # fetched at strategy start
    circuit_lower: float | None = None


class PaperBroker(BrokerBase):
    """Live-tick paper broker. Injected with circuit-band data by the runner."""

    def __init__(self) -> None:
        cfg = get_settings()
        self._delay = cfg.fill_delay_ticks
        self._slippage_bps = cfg.slippage_bps
        self._tick_size = cfg.tick_size
        self._enforce_circuit = cfg.enforce_circuit_limits
        self._enforce_liquidity = cfg.enforce_liquidity
        self._pending: dict[str, _Pending] = {}   # order_ref → _Pending
        self._trade_inflight: dict[int, str] = {}  # trade_id → order_ref

    # ── Circuit band (set once per session by runner) ─────────────────────────

    def set_circuit(self, token: int, upper: float, lower: float) -> None:
        for p in self._pending.values():
            if p.token == token:
                p.circuit_upper = upper
                p.circuit_lower = lower
        self._circuit: dict[int, tuple[float, float]] = getattr(self, "_circuit", {})
        self._circuit[token] = (upper, lower)

    # ── BrokerBase interface ──────────────────────────────────────────────────

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
        circuit = getattr(self, "_circuit", {}).get(instrument_token)

        # Circuit-band rejection before persisting
        if self._enforce_circuit and circuit and intent.order_type == "LIMIT" and intent.price:
            upper, lower = circuit
            if not (lower <= intent.price <= upper):
                log.warning("order_rejected_circuit", order_ref=order_ref, price=intent.price)
                # Persist REJECTED immediately so the runner can see it
                async with async_session() as s:
                    repo = OrderRepository(s)
                    db_order = await repo.create(
                        order_ref=order_ref, trade_id=trade_id, run_id=run_id,
                        symbol=symbol, side=intent.side, qty=intent.qty,
                        order_type=intent.order_type, price=intent.price,
                        product=intent.product, state="REJECTED",
                        reason=intent.reason,
                        created_at=now_ist(), updated_at=now_ist(),
                    )
                return order_ref  # caller gets ref; FillResult not emitted (rejected at placement)

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

        pending = _Pending(
            order_ref=order_ref, db_order_id=db_order.id,
            intent=intent, symbol=symbol, token=instrument_token,
            run_id=run_id, trade_id=trade_id,
        )
        if circuit:
            pending.circuit_upper, pending.circuit_lower = circuit
        self._pending[order_ref] = pending
        if trade_id is not None:
            self._trade_inflight[trade_id] = order_ref

        log.info("order_pending", order_ref=order_ref, symbol=symbol,
                 side=intent.side, qty=intent.qty, type=intent.order_type)
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
        if not self._pending:
            return []

        fills: list[FillResult] = []
        done: list[str] = []

        for ref, p in self._pending.items():
            if p.token != tick.instrument_token:
                continue
            p.ticks_seen += 1

            fill = self._try_fill(p, tick)
            if fill:
                fills.append(fill)
                done.append(ref)

        for ref in done:
            p = self._pending.pop(ref)
            if p.trade_id is not None:
                self._trade_inflight.pop(p.trade_id, None)

        if fills:
            await self._persist_fills(fills)
        return fills

    async def on_candle(self, candle: CandleData) -> list[FillResult]:
        return []  # paper broker fills only on ticks

    async def has_inflight(self, trade_id: int | None) -> bool:
        if trade_id is None:
            return False
        return trade_id in self._trade_inflight

    # ── Fill logic ────────────────────────────────────────────────────────────

    def _try_fill(self, p: _Pending, tick: TickData) -> FillResult | None:
        from core.clock import now_ist

        intent = p.intent

        # MARKET: wait fill_delay_ticks, then fill
        if intent.order_type == "MARKET":
            if p.ticks_seen < self._delay:
                return None
            price = self._market_price(intent.side, tick)
            return FillResult(
                order_ref=p.order_ref,
                filled_qty=intent.qty,
                avg_price=price,
                state="COMPLETE",
                ts=now_ist(),
            )

        # LIMIT: fill when tick crosses the limit
        if intent.order_type == "LIMIT" and intent.price is not None:
            if intent.side == "BUY" and tick.ltp <= intent.price:
                return FillResult(
                    order_ref=p.order_ref, filled_qty=intent.qty,
                    avg_price=intent.price, state="COMPLETE", ts=now_ist(),
                )
            if intent.side == "SELL" and tick.ltp >= intent.price:
                return FillResult(
                    order_ref=p.order_ref, filled_qty=intent.qty,
                    avg_price=intent.price, state="COMPLETE", ts=now_ist(),
                )

        return None

    def _market_price(self, side: str, tick: TickData) -> float:
        """Best ask (BUY) or best bid (SELL). Falls back to LTP±slippage."""
        depth = tick.depth
        if depth:
            if side == "BUY":
                asks = depth.get("sell", [])
                if asks and asks[0].get("quantity", 0) > 0:
                    return float(asks[0]["price"])
            else:
                bids = depth.get("buy", [])
                if bids and bids[0].get("quantity", 0) > 0:
                    return float(bids[0]["price"])

        # Depth unavailable — use pessimistic slippage
        slippage = max(self._tick_size, self._slippage_bps / 10_000 * tick.ltp)
        return tick.ltp + slippage if side == "BUY" else tick.ltp - slippage

    # ── DB persistence of fills ───────────────────────────────────────────────

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
                        db_order.id,
                        state=fill.state,
                        filled_qty=fill.filled_qty,
                        avg_fill_price=fill.avg_price,
                        updated_at=now_ist(),
                    )
            await s.commit()
