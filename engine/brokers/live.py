"""LiveBroker — Kite REST order placement with idempotency and retries.

Order lifecycle (per docs/execution-spec.md §4):
  place_order()  → persist CREATED (order_ref) → call Kite → store broker_order_id → PENDING
  on_tick()      → poll Kite order for status updates; transition DB state on change
  cancel_order() → Kite cancel + DB CANCELLED

Idempotency:
  Before any retry, fetch Kite orders by tag=order_ref; if found, do not re-submit.

Retries:
  Transient errors (network, HTTP 5xx, 429): exponential backoff up to max_order_retries.
  Hard rejects (Kite 400 / InputException): not retried.

Reconciliation (called by runner.start()):
  Fetches Kite positions + order book; compares to DB.
  Mismatches → engine enters SAFE mode.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from kiteconnect import exceptions as KiteExc

from core.clock import now_ist
from core.config import get_settings
from core.logging import get_logger
from engine.brokers.base import BrokerBase, FillResult
from engine.data.types import CandleData, TickData
from engine.strategy.order import StrategyOrder

log = get_logger(__name__)


# Kite final states that mean the order is done
_KITE_FINAL = {"COMPLETE", "REJECTED", "CANCELLED"}
_KITE_TO_ENGINE = {
    "COMPLETE": "COMPLETE",
    "REJECTED": "REJECTED",
    "CANCELLED": "CANCELLED",
    "OPEN": "OPEN",
    "PENDING": "PENDING",
    "OPEN PENDING": "PENDING",
    "AMO REQ RECEIVED": "PENDING",
    "MODIFIED": "OPEN",
    "TRIGGER PENDING": "PENDING",
}


@dataclass
class _LivePending:
    order_ref: str
    db_order_id: int
    broker_order_id: str | None
    intent: StrategyOrder
    symbol: str
    token: int
    run_id: int
    trade_id: int | None
    poll_count: int = 0


class LiveBroker(BrokerBase):
    """Kite REST live broker. Polls order status on each on_tick() call."""

    # Poll Kite order status every N ticks (polling fallback for postback failures)
    POLL_EVERY_TICKS = 5

    def __init__(self) -> None:
        cfg = get_settings()
        self._max_retries = cfg.max_order_retries
        self._pending: dict[str, _LivePending] = {}
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
        from db.base import async_session
        from db.repositories import OrderRepository
        from integrations.kite import orders as kite_orders

        order_ref = self.new_ref()
        exchange = symbol.split(":")[0] if ":" in symbol else "NSE"
        sym = symbol.split(":")[-1] if ":" in symbol else symbol

        # Persist CREATED before touching Kite (crash-safe)
        async with async_session() as s:
            repo = OrderRepository(s)
            db_order = await repo.create(
                order_ref=order_ref, trade_id=trade_id, run_id=run_id,
                symbol=symbol, side=intent.side, qty=intent.qty,
                order_type=intent.order_type, price=intent.price,
                product=intent.product, state="CREATED",
                reason=intent.reason,
                created_at=now_ist(), updated_at=now_ist(),
            )

        # Submit to Kite with retry
        broker_order_id: str | None = None
        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                broker_order_id = await kite_orders.place_order(
                    symbol=sym, exchange=exchange,
                    side=intent.side, qty=intent.qty,
                    order_type=intent.order_type, price=intent.price,
                    product=intent.product, tag=order_ref[:20],
                )
                break
            except (KiteExc.InputException, KiteExc.DataException) as exc:
                # Hard reject — do not retry
                log.error("kite_hard_reject", error=str(exc), order_ref=order_ref)
                await self._transition_db(db_order.id, "REJECTED", reason=str(exc))
                return order_ref
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                wait = 2 ** attempt
                log.warning("kite_transient_error", attempt=attempt, wait=wait, error=str(exc))

                # Idempotency check before retry: did Kite actually receive it?
                existing = await self._find_by_tag(order_ref[:20])
                if existing:
                    broker_order_id = existing["order_id"]
                    log.info("kite_order_found_on_retry", broker_order_id=broker_order_id)
                    break

                await asyncio.sleep(wait)

        if broker_order_id is None:
            log.error("kite_order_failed_all_retries", order_ref=order_ref, error=str(last_exc))
            await self._transition_db(db_order.id, "REJECTED")
            return order_ref

        # Move to PENDING with broker_order_id stored
        await self._transition_db(db_order.id, "PENDING", broker_order_id=broker_order_id)

        p = _LivePending(
            order_ref=order_ref, db_order_id=db_order.id,
            broker_order_id=broker_order_id, intent=intent,
            symbol=symbol, token=instrument_token,
            run_id=run_id, trade_id=trade_id,
        )
        self._pending[order_ref] = p
        if trade_id is not None:
            self._trade_inflight[trade_id] = order_ref

        log.info("live_order_pending", order_ref=order_ref, broker_order_id=broker_order_id)
        return order_ref

    async def cancel_order(self, order_ref: str) -> bool:
        from integrations.kite import orders as kite_orders

        p = self._pending.pop(order_ref, None)
        if p is None:
            return False
        if p.trade_id is not None:
            self._trade_inflight.pop(p.trade_id, None)

        if p.broker_order_id:
            try:
                await kite_orders.cancel_order(p.broker_order_id)
            except Exception as exc:  # noqa: BLE001
                log.warning("kite_cancel_failed", broker_order_id=p.broker_order_id, error=str(exc))

        await self._transition_db(p.db_order_id, "CANCELLED")
        return True

    async def on_tick(self, tick: TickData) -> list[FillResult]:
        """Poll Kite order status every POLL_EVERY_TICKS ticks."""
        if not self._pending:
            return []

        fills: list[FillResult] = []
        done: list[str] = []

        for ref, p in self._pending.items():
            if p.broker_order_id is None:
                continue
            p.poll_count += 1
            if p.poll_count % self.POLL_EVERY_TICKS != 0:
                continue

            fill = await self._poll_kite(p)
            if fill:
                fills.append(fill)
                done.append(ref)

        for ref in done:
            p = self._pending.pop(ref)
            if p.trade_id is not None:
                self._trade_inflight.pop(p.trade_id, None)

        return fills

    async def on_candle(self, candle: CandleData) -> list[FillResult]:
        return []  # live broker fills via Kite postback / polling, not candles

    async def has_inflight(self, trade_id: int | None) -> bool:
        if trade_id is None:
            return False
        return trade_id in self._trade_inflight

    # ── Postback consumer (called by API route) ───────────────────────────────

    async def handle_postback(self, data: dict) -> FillResult | None:
        """Process a Kite postback webhook payload."""
        tag = data.get("tag", "")
        order_id = str(data.get("order_id", ""))
        status = data.get("status", "").upper()
        filled_qty = int(data.get("filled_quantity", 0))
        avg_price = float(data.get("average_price", 0.0))

        # Locate the pending order by tag (= order_ref[:20])
        p = next((v for v in self._pending.values() if v.order_ref[:20] == tag), None)
        if p is None:
            return None

        engine_state = _KITE_TO_ENGINE.get(status, status)
        await self._transition_db(
            p.db_order_id, engine_state,
            broker_order_id=order_id,
            filled_qty=filled_qty,
            avg_fill_price=avg_price,
        )

        if engine_state in ("COMPLETE",):
            fill = FillResult(
                order_ref=p.order_ref, filled_qty=filled_qty,
                avg_price=avg_price, state="COMPLETE", ts=now_ist(),
            )
            self._pending.pop(p.order_ref, None)
            if p.trade_id is not None:
                self._trade_inflight.pop(p.trade_id, None)
            return fill

        return None

    # ── Reconciliation ────────────────────────────────────────────────────────

    async def reconcile(self, run_id: int) -> list[str]:
        """Compare DB open orders to Kite's actual order book.
        Returns list of mismatch descriptions (empty = clean).
        """
        from integrations.kite import orders as kite_orders

        kite_orders_list = await kite_orders.get_all_orders()
        kite_by_id = {str(o["order_id"]): o for o in kite_orders_list}
        mismatches = []

        for ref, p in list(self._pending.items()):
            if not p.broker_order_id:
                continue
            kite_order = kite_by_id.get(p.broker_order_id)
            if not kite_order:
                mismatches.append(f"Order {p.order_ref[:8]} not found in Kite order book")
                continue
            kite_status = kite_order.get("status", "").upper()
            engine_status = _KITE_TO_ENGINE.get(kite_status, kite_status)
            if engine_status in _KITE_FINAL:
                # Order finished on Kite but we didn't receive postback — resolve it
                filled_qty = int(kite_order.get("filled_quantity", 0))
                avg_price = float(kite_order.get("average_price", 0.0))
                await self._transition_db(
                    p.db_order_id, engine_status,
                    filled_qty=filled_qty, avg_fill_price=avg_price,
                )
                self._pending.pop(ref)
                if p.trade_id is not None:
                    self._trade_inflight.pop(p.trade_id, None)

        return mismatches

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _poll_kite(self, p: _LivePending) -> FillResult | None:
        from integrations.kite import orders as kite_orders

        try:
            order = await kite_orders.get_order(p.broker_order_id)
        except Exception as exc:  # noqa: BLE001
            log.warning("kite_poll_error", broker_order_id=p.broker_order_id, error=str(exc))
            return None

        if not order:
            return None

        kite_status = order.get("status", "").upper()
        engine_state = _KITE_TO_ENGINE.get(kite_status, kite_status)
        filled_qty = int(order.get("filled_quantity", 0))
        avg_price = float(order.get("average_price", 0.0))

        await self._transition_db(p.db_order_id, engine_state,
                                  filled_qty=filled_qty, avg_fill_price=avg_price)

        if engine_state == "COMPLETE":
            return FillResult(
                order_ref=p.order_ref, filled_qty=filled_qty,
                avg_price=avg_price, state="COMPLETE", ts=now_ist(),
            )
        return None

    async def _transition_db(self, db_order_id: int, state: str, **kw) -> None:
        from db.base import async_session
        from db.repositories import OrderRepository

        async with async_session() as s:
            repo = OrderRepository(s)
            await repo.transition(db_order_id, state=state, updated_at=now_ist(), **kw)
            await s.commit()

    async def _find_by_tag(self, tag: str) -> dict | None:
        from integrations.kite import orders as kite_orders

        try:
            all_orders = await kite_orders.get_all_orders()
            return next((o for o in all_orders if o.get("tag") == tag), None)
        except Exception:  # noqa: BLE001
            return None
