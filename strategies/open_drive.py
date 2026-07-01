"""Open-Drive — enter at the open, ride it with a ratcheting trailing stop.

Two runnable variants share one engine:
    open_drive.Long   — buys at the open
    open_drive.Short  — sells (shorts) at the open

Behaviour (per variant):
1. ENTRY  — open the position on the first tick of the trading session, as long as
   it arrives within `entry_window_min` minutes of 09:15 IST. One entry per day.
2. STOP   — until the trade runs `arm_pct` in your favour, a fixed stop sits
   `init_stop_pct` adverse to the entry price.
3. TRAIL  — once `arm_pct` favourable is reached, the stop *ratchets*: it climbs one
   `trail_step_pct` notch for every `trail_step_pct` of new favourable progress, and
   never moves back. Exit when price falls to the current stop.

The engine separately force-squares-off any open position at 15:15 IST, so this
strategy does not need an end-of-day timer.

All percentages are fractions: 0.01 = 1%, 0.002 = 0.2%.
"""

from __future__ import annotations

import math

from engine.data.types import TickData
from engine.strategy import BaseStrategy, Position, StrategyOrder


class _OpenDrive(BaseStrategy):
    """Shared logic for the long and short variants. Not runnable on its own."""

    abstract = True              # loader skips this; only Long/Short are selectable
    direction: str = ""          # "LONG" | "SHORT" — set by the concrete subclass

    instrument = "NSE:SBIN"
    timeframe = "minute"
    params: dict = {
        "qty": 10,
        "init_stop_pct": 0.01,    # 1% fixed stop before trailing arms
        "arm_pct": 0.01,          # favourable move that switches fixed → trailing
        "trail_step_pct": 0.002,  # 0.2% ratchet step
        "entry_window_min": 5,    # only enter within N minutes of the open
    }
    param_schema = {
        "qty":             {"type": int,   "min": 1},
        "init_stop_pct":   {"type": float, "min": 0.0, "max": 0.5},
        "arm_pct":         {"type": float, "min": 0.0, "max": 0.5},
        "trail_step_pct":  {"type": float, "min": 0.0001, "max": 0.1},
        "entry_window_min": {"type": int,  "min": 0},
    }

    def on_start(self) -> None:
        # Per-day entry latch — prevents re-entry after an intraday restart.
        self._entered_date: str | None = None

    # ── Entry ──────────────────────────────────────────────────────────────────

    def entry(self, tick: TickData) -> StrategyOrder | None:
        today = self._session_date  # set by the engine's _observe() before this hook
        if self._entered_date == today:
            return None  # already took today's trade
        if not self.first_tick_of_session:
            return None  # only fire on the session's opening tick
        if self.minutes_since_open(tick) > self.params["entry_window_min"]:
            return None  # missed the open window (e.g. engine started mid-session)

        self._entered_date = today
        qty = self.params["qty"]
        self.log("open_drive_entry", direction=self.direction, price=tick.ltp,
                 day_open=self.day_open)
        return self.buy(qty=qty) if self.direction == "LONG" else self.sell(qty=qty)

    # ── In-position bookkeeping ────────────────────────────────────────────────

    def _favourable_pct(self, pos: Position) -> float:
        """Signed progress in our favour as a fraction of entry price."""
        move = (pos.ltp - pos.entry_price) / pos.entry_price
        return move if self.direction == "LONG" else -move

    def on_tick(self, tick: TickData, pos: Position) -> None:
        fav = self._favourable_pct(pos)
        peak = max(pos.vars.get("peak_fav", fav), fav)
        pos.vars["peak_fav"] = peak

        arm_pct = self.params["arm_pct"]
        step = self.params["trail_step_pct"]

        if not pos.vars.get("armed", False) and peak >= arm_pct:
            pos.vars["armed"] = True

        if pos.vars.get("armed", False):
            # Ratchet: highest notch fully reached, trailing one step behind the peak.
            notches = math.floor(peak / step)
            pos.vars["stop_fav"] = (notches - 1) * step
        else:
            # Fixed pre-arm stop, init_stop_pct adverse to entry.
            pos.vars["stop_fav"] = -self.params["init_stop_pct"]

    def exit(self, tick: TickData, pos: Position) -> bool:
        stop_fav = pos.vars.get("stop_fav", -self.params["init_stop_pct"])
        return self._favourable_pct(pos) <= stop_fav

    def on_stop(self) -> None:
        self.log("open_drive_stopped", direction=self.direction)


class Long(_OpenDrive):
    """Open-Drive, long side — buys at the open."""

    direction = "LONG"


class Short(_OpenDrive):
    """Open-Drive, short side — sells (shorts) at the open."""

    direction = "SHORT"
