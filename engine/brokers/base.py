"""BrokerBase — the interface every broker implementation satisfies.

Three concrete brokers implement this contract:
  PaperBroker   — simulated fills on live ticks (Task 05)
  BacktestBroker — OHLC / tick-replay fills (Task 05)
  LiveBroker    — Kite REST orders (Task 07)

The engine runner codes only to BrokerBase; swapping brokers never touches strategy code.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from engine.data.types import CandleData, TickData
from engine.strategy.order import StrategyOrder


@dataclass
class FillResult:
    """Outcome of an order fill (or rejection / cancellation)."""

    order_ref: str
    filled_qty: int
    avg_price: float
    state: str          # COMPLETE | PARTIAL | REJECTED | CANCELLED
    ts: datetime
    reason: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class BrokerBase(ABC):
    """Abstract broker — all engine interactions go through this interface."""

    # ── Placement ─────────────────────────────────────────────────────────────

    @abstractmethod
    async def place_order(
        self,
        intent: StrategyOrder,
        *,
        symbol: str,
        instrument_token: int,
        run_id: int,
        trade_id: int | None = None,
    ) -> str:
        """Persist a CREATED order, queue it for execution.

        Returns the order_ref (UUID4 string) — the idempotency key.
        Raises if a duplicate order_ref is detected.
        """

    @abstractmethod
    async def cancel_order(self, order_ref: str) -> bool:
        """Cancel a pending/open order. Returns True if the order was found and cancelled."""

    # ── Fill processing ───────────────────────────────────────────────────────

    @abstractmethod
    async def on_tick(self, tick: TickData) -> list[FillResult]:
        """Process pending orders against the incoming tick.

        Returns a list of fills that completed on this tick.
        Caller is responsible for updating trade/position state.
        """

    @abstractmethod
    async def on_candle(self, candle: CandleData) -> list[FillResult]:
        """Process pending orders against a completed candle (OHLC backtest mode).

        Live and paper brokers return [] — candle-based fills only apply to OHLC backtest.
        """

    # ── Guard ─────────────────────────────────────────────────────────────────

    @abstractmethod
    async def has_inflight(self, trade_id: int | None) -> bool:
        """Return True if there's a PENDING/OPEN order for this trade.

        Used to prevent duplicate entries/exits — the engine checks this before
        calling place_order().
        """

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Optional: called once by the runner before market open."""

    async def stop(self) -> None:
        """Optional: called on graceful shutdown."""

    # ── Utility ───────────────────────────────────────────────────────────────

    @staticmethod
    def new_ref() -> str:
        return str(uuid.uuid4())
