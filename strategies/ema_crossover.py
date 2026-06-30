"""EMA crossover with trailing cutoff — the canonical reference strategy.

Logic:
- Enter LONG when fast EMA crosses above slow EMA AND LTP > slow EMA.
- Track peak LTP in pos.vars; exit when LTP drops below peak * trail_pct.
- Param-schema enforced at load time.
"""

from __future__ import annotations

from engine.data.types import TickData
from engine.strategy import EMA, BaseStrategy, StrategyOrder
from engine.strategy.position import Position


class Strategy(BaseStrategy):
    instrument = "NSE:SBIN"
    timeframe = "5minute"
    params: dict = {"qty": 10, "fast": 9, "slow": 21, "trail_pct": 0.99}
    param_schema = {
        "qty":       {"type": int,   "min": 1},
        "fast":      {"type": int,   "min": 2},
        "slow":      {"type": int,   "min": 3},
        "trail_pct": {"type": float, "min": 0.9, "max": 1.0},
    }

    def on_start(self) -> None:
        self.fast_ema = self.indicator(EMA, self.params["fast"])
        self.slow_ema = self.indicator(EMA, self.params["slow"])
        self._prev_fast: float | None = None
        self._prev_slow: float | None = None

    def entry(self, tick: TickData) -> StrategyOrder | None:
        fv = self.fast_ema.value
        sv = self.slow_ema.value
        if fv is None or sv is None:
            return None
        # Crossover: fast was below slow, now above; price above slow EMA
        crossed_up = (
            self._prev_fast is not None
            and self._prev_slow is not None
            and self._prev_fast <= self._prev_slow
            and fv > sv
        )
        self._prev_fast = fv
        self._prev_slow = sv
        if crossed_up and tick.ltp > sv:
            return self.buy(qty=self.params["qty"])
        return None

    def on_tick(self, tick: TickData, pos: Position) -> None:
        peak = pos.vars.get("peak", tick.ltp)
        pos.vars["peak"] = max(peak, tick.ltp)
        pos.vars["cutoff"] = pos.vars["peak"] * self.params["trail_pct"]

    def exit(self, tick: TickData, pos: Position) -> bool:
        cutoff = pos.vars.get("cutoff", 0.0)
        return tick.ltp <= cutoff

    def on_stop(self) -> None:
        self.log("strategy stopped", fast=self.params["fast"], slow=self.params["slow"])
