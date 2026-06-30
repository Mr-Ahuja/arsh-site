"""Built-in indicators — registered in on_start(), fed automatically by the engine.

Strategies read indicator.value; they never call update methods directly.
The engine calls on_candle() or on_tick() depending on the indicator's feed mode.

Supported indicators: EMA, SMA, RSI, ATR, VWAP
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque

from engine.data.types import CandleData, TickData


class Indicator(ABC):
    """Abstract base. Subclasses implement on_candle and/or on_tick."""

    feed: str = "candle"  # "candle" (default) | "tick"

    @property
    @abstractmethod
    def value(self) -> float | None:
        """Current indicator value, or None if not yet warmed up."""

    def on_candle(self, candle: CandleData) -> None:
        """Engine calls this on each completed candle (when feed='candle' or always)."""

    def on_tick(self, tick: TickData) -> None:
        """Engine calls this on each tick (only when feed='tick')."""

    def reset(self) -> None:
        """Reset state — called at session start for intraday indicators (e.g. VWAP)."""


# ── EMA ───────────────────────────────────────────────────────────────────────

class EMA(Indicator):
    """Exponential Moving Average (Wilder's EMA convention: multiplier = 2/(period+1))."""

    def __init__(self, period: int, feed: str = "candle") -> None:
        if period < 1:
            raise ValueError(f"EMA period must be >= 1, got {period}")
        self.period = period
        self.feed = feed
        self._multiplier = 2.0 / (period + 1)
        self._value: float | None = None
        self._seed_prices: list[float] = []

    @property
    def value(self) -> float | None:
        return self._value

    def _update(self, price: float) -> None:
        if self._value is None:
            self._seed_prices.append(price)
            if len(self._seed_prices) >= self.period:
                self._value = sum(self._seed_prices) / len(self._seed_prices)
        else:
            self._value = price * self._multiplier + self._value * (1 - self._multiplier)

    def on_candle(self, candle: CandleData) -> None:
        self._update(candle.close)

    def on_tick(self, tick: TickData) -> None:
        self._update(tick.ltp)


# ── SMA ───────────────────────────────────────────────────────────────────────

class SMA(Indicator):
    """Simple Moving Average."""

    def __init__(self, period: int, feed: str = "candle") -> None:
        if period < 1:
            raise ValueError(f"SMA period must be >= 1, got {period}")
        self.period = period
        self.feed = feed
        self._window: deque[float] = deque(maxlen=period)

    @property
    def value(self) -> float | None:
        if len(self._window) < self.period:
            return None
        return sum(self._window) / self.period

    def _update(self, price: float) -> None:
        self._window.append(price)

    def on_candle(self, candle: CandleData) -> None:
        self._update(candle.close)

    def on_tick(self, tick: TickData) -> None:
        self._update(tick.ltp)


# ── RSI ───────────────────────────────────────────────────────────────────────

class RSI(Indicator):
    """Relative Strength Index (Wilder's smoothing)."""

    def __init__(self, period: int = 14, feed: str = "candle") -> None:
        if period < 2:
            raise ValueError(f"RSI period must be >= 2, got {period}")
        self.period = period
        self.feed = feed
        self._prev_price: float | None = None
        self._avg_gain: float | None = None
        self._avg_loss: float | None = None
        self._seed_gains: list[float] = []
        self._seed_losses: list[float] = []

    @property
    def value(self) -> float | None:
        if self._avg_gain is None or self._avg_loss is None:
            return None
        if self._avg_loss == 0:
            return 100.0
        rs = self._avg_gain / self._avg_loss
        return 100.0 - 100.0 / (1.0 + rs)

    def _update(self, price: float) -> None:
        if self._prev_price is None:
            self._prev_price = price
            return
        change = price - self._prev_price
        self._prev_price = price
        gain = max(change, 0.0)
        loss = abs(min(change, 0.0))

        if self._avg_gain is None:
            self._seed_gains.append(gain)
            self._seed_losses.append(loss)
            if len(self._seed_gains) >= self.period:
                self._avg_gain = sum(self._seed_gains) / self.period
                self._avg_loss = sum(self._seed_losses) / self.period
        else:
            self._avg_gain = (self._avg_gain * (self.period - 1) + gain) / self.period
            self._avg_loss = (self._avg_loss * (self.period - 1) + loss) / self.period

    def on_candle(self, candle: CandleData) -> None:
        self._update(candle.close)

    def on_tick(self, tick: TickData) -> None:
        self._update(tick.ltp)


# ── ATR ───────────────────────────────────────────────────────────────────────

class ATR(Indicator):
    """Average True Range (Wilder's smoothing). Meaningful only on candle feed."""

    def __init__(self, period: int = 14, feed: str = "candle") -> None:
        if period < 1:
            raise ValueError(f"ATR period must be >= 1, got {period}")
        self.period = period
        self.feed = feed
        self._prev_close: float | None = None
        self._atr: float | None = None
        self._seed_trs: list[float] = []

    @property
    def value(self) -> float | None:
        return self._atr

    def _true_range(self, high: float, low: float, prev_close: float) -> float:
        return max(high - low, abs(high - prev_close), abs(low - prev_close))

    def on_candle(self, candle: CandleData) -> None:
        if self._prev_close is None:
            self._prev_close = candle.close
            return
        tr = self._true_range(candle.high, candle.low, self._prev_close)
        self._prev_close = candle.close
        if self._atr is None:
            self._seed_trs.append(tr)
            if len(self._seed_trs) >= self.period:
                self._atr = sum(self._seed_trs) / self.period
        else:
            self._atr = (self._atr * (self.period - 1) + tr) / self.period

    def on_tick(self, tick: TickData) -> None:
        pass  # ATR is not meaningful on raw ticks (no high/low)


# ── VWAP ──────────────────────────────────────────────────────────────────────

class VWAP(Indicator):
    """Volume Weighted Average Price — resets each trading session.

    Candle feed: typical price = (H+L+C)/3
    Tick feed:   price = ltp, volume = last_traded_qty
    """

    def __init__(self, feed: str = "candle") -> None:
        self.feed = feed
        self._cum_pv: float = 0.0   # cumulative price × volume
        self._cum_vol: int = 0

    @property
    def value(self) -> float | None:
        if self._cum_vol == 0:
            return None
        return self._cum_pv / self._cum_vol

    def reset(self) -> None:
        self._cum_pv = 0.0
        self._cum_vol = 0

    def on_candle(self, candle: CandleData) -> None:
        typical = (candle.high + candle.low + candle.close) / 3.0
        self._cum_pv += typical * candle.volume
        self._cum_vol += candle.volume

    def on_tick(self, tick: TickData) -> None:
        if tick.qty > 0:
            self._cum_pv += tick.ltp * tick.qty
            self._cum_vol += tick.qty


# ── Registry ─────────────────────────────────────────────────────────────────

INDICATOR_REGISTRY: dict[str, type[Indicator]] = {
    "EMA": EMA,
    "SMA": SMA,
    "RSI": RSI,
    "ATR": ATR,
    "VWAP": VWAP,
}
