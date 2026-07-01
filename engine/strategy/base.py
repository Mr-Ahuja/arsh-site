"""BaseStrategy — the contract every user strategy subclasses.

Drop a file in strategies/, subclass BaseStrategy, implement the lifecycle hooks.
The engine discovers, loads, instantiates, and runs it. No engine edits needed.

Minimal example:
    class Strategy(BaseStrategy):
        instrument = "NSE:SBIN"
        timeframe  = "5minute"
        params     = {"qty": 10}

        def on_start(self):
            self.ema = self.indicator(EMA, 20)

        def entry(self, tick):
            if self.ema.value and tick.ltp > self.ema.value:
                return self.buy(qty=self.params["qty"])

        def on_tick(self, tick, pos):
            pos.vars["peak"] = max(pos.vars.get("peak", tick.ltp), tick.ltp)

        def exit(self, tick, pos):
            return tick.ltp <= pos.vars.get("peak", 0) * 0.99
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import TYPE_CHECKING, Any

from core.clock import IST, MARKET_OPEN, now_ist
from core.logging import get_logger
from engine.data.types import CandleData, TickData
from engine.strategy.indicators import Indicator
from engine.strategy.order import StrategyOrder
from engine.strategy.position import Position

if TYPE_CHECKING:
    from engine.data.buffer import RollingBuffer

log = get_logger(__name__)

# Hook timing thresholds (seconds)
_SOFT_TIMEOUT = 0.050   # 50 ms — log a warning
_HARD_TIMEOUT = 0.200   # 200 ms — log an error; repeated hits halt the strategy


class StrategyError(Exception):
    """Raised when a hook violates the contract (wrong return type, timeout, etc.)."""


class BaseStrategy:
    """Abstract base. Subclass and implement the hooks you need."""

    # ── Class-level declarations (override in your subclass) ──────────────────

    instrument: str = ""          # e.g. "NSE:SBIN"
    timeframe: str = "5minute"    # candle interval
    params: dict[str, Any] = {}   # tunables; overridable per run
    param_schema: dict[str, Any] = {}  # optional validation schema
    abstract: bool = False        # mark True on shared base classes; loader skips them

    # ── Engine-injected (set by loader before on_start) ───────────────────────

    _buffer: RollingBuffer
    _run_id: int | None = None
    _mode: str = "paper"

    def __init__(self) -> None:
        self._indicators: list[Indicator] = []
        self._hard_overruns: int = 0
        # Session tracking — populated by the engine via _observe() on each tick
        self._session_date: str | None = None
        self.day_open: float | None = None          # first price seen this IST session
        self.first_tick_of_session: bool = False     # True only on the day's first tick

    # ── Time / session helpers ────────────────────────────────────────────────

    def now_ist(self) -> datetime:
        """Current wall-clock time in IST. Use this instead of datetime.now()."""
        return now_ist()

    def minutes_since_open(self, tick: TickData) -> float:
        """Minutes elapsed since 09:15 IST for this tick (negative before open)."""
        t = tick.ts.astimezone(IST)
        open_dt = t.replace(
            hour=MARKET_OPEN.hour, minute=MARKET_OPEN.minute, second=0, microsecond=0
        )
        return (t - open_dt).total_seconds() / 60.0

    def _observe(self, tick: TickData) -> None:
        """Engine-internal: called once per tick before hooks. Tracks the session's
        opening price and flags the first tick of each new IST trading day."""
        day = tick.ts.astimezone(IST).strftime("%Y-%m-%d")
        if day != self._session_date:
            self._session_date = day
            self.day_open = tick.ltp
            self.first_tick_of_session = True
        else:
            self.first_tick_of_session = False

    # ── Lifecycle hooks (implement in your subclass) ───────────────────────────

    def on_start(self) -> None:
        """Called once before any ticks. Register indicators, set up state."""

    def entry(self, tick: TickData) -> StrategyOrder | None:
        """Called every tick while flat. Return self.buy()/self.sell() or None."""
        return None

    def on_tick(self, tick: TickData, pos: Position) -> None:
        """Called every tick while in a position. Mutate pos.vars here."""

    def exit(self, tick: TickData, pos: Position) -> bool:
        """Called every tick while in a position. Return True to square off."""
        return False

    def on_order_update(self, order: StrategyOrder) -> None:
        """Optional. Called when an order fill/reject/cancel arrives."""

    def on_stop(self) -> None:
        """Called once at shutdown or forced square-off."""

    # ── Order helpers (call from entry / exit hooks) ───────────────────────────

    def buy(
        self,
        qty: int,
        type: str = "MARKET",  # noqa: A002
        price: float | None = None,
    ) -> StrategyOrder:
        return StrategyOrder(side="BUY", qty=qty, order_type=type, price=price)

    def sell(
        self,
        qty: int,
        type: str = "MARKET",  # noqa: A002
        price: float | None = None,
    ) -> StrategyOrder:
        return StrategyOrder(side="SELL", qty=qty, order_type=type, price=price)

    def square_off(self, reason: str = "strategy") -> StrategyOrder:
        """Signal an immediate exit of the current position."""
        return StrategyOrder(side="SELL", qty=0, reason=reason)  # engine fills actual qty

    # ── Indicator helper ──────────────────────────────────────────────────────

    def indicator(self, cls: type[Indicator], *args: Any, **kwargs: Any) -> Indicator:
        """Register and return an indicator. The engine feeds it; you only read .value.

        Example:
            self.ema = self.indicator(EMA, 20)
            self.vwap = self.indicator(VWAP, feed="tick")
        """
        ind = cls(*args, **kwargs)
        self._indicators.append(ind)
        return ind

    # ── Data helpers ──────────────────────────────────────────────────────────

    def candles(self, n: int = 50) -> list[CandleData]:
        """Last N completed candles (oldest first)."""
        return self._buffer.last_n_candles(n)

    def log(self, msg: str, level: str = "info", **kw: Any) -> None:
        """Structured log. Use this instead of print() — it stays off the hot path."""
        getattr(log, level, log.info)(msg, strategy=self.__class__.__name__, **kw)

    # ── Engine-internal: hook dispatch with timing guard ──────────────────────

    def _call_entry(self, tick: TickData) -> StrategyOrder | None:
        result = self._timed_call("entry", self.entry, tick)
        if result is not None and not isinstance(result, StrategyOrder):
            raise StrategyError(
                f"entry() must return StrategyOrder or None, got {type(result).__name__}"
            )
        return result

    def _call_on_tick(self, tick: TickData, pos: Position) -> None:
        self._timed_call("on_tick", self.on_tick, tick, pos)

    def _call_exit(self, tick: TickData, pos: Position) -> bool:
        result = self._timed_call("exit", self.exit, tick, pos)
        if not isinstance(result, bool):
            raise StrategyError(
                f"exit() must return bool, got {type(result).__name__}"
            )
        return result

    def _timed_call(self, name: str, fn: Any, *args: Any) -> Any:
        t0 = time.perf_counter()
        result = fn(*args)
        elapsed = time.perf_counter() - t0
        if elapsed > _HARD_TIMEOUT:
            self._hard_overruns += 1
            log.error(
                "hook_hard_timeout",
                hook=name,
                elapsed_ms=round(elapsed * 1000, 1),
                overruns=self._hard_overruns,
            )
        elif elapsed > _SOFT_TIMEOUT:
            log.warning("hook_soft_timeout", hook=name, elapsed_ms=round(elapsed * 1000, 1))
        return result

    # ── Engine-internal: feed indicators ─────────────────────────────────────

    def _feed_candle(self, candle: CandleData) -> None:
        for ind in self._indicators:
            try:
                ind.on_candle(candle)
            except Exception as exc:  # noqa: BLE001
                log.error("indicator_error", indicator=type(ind).__name__, error=str(exc))

    def _feed_tick(self, tick: TickData) -> None:
        for ind in self._indicators:
            if ind.feed == "tick":
                try:
                    ind.on_tick(tick)
                except Exception as exc:  # noqa: BLE001
                    log.error("indicator_error", indicator=type(ind).__name__, error=str(exc))

    def _reset_session_indicators(self) -> None:
        """Call at market open — lets intraday indicators (VWAP) reset."""
        for ind in self._indicators:
            ind.reset()
