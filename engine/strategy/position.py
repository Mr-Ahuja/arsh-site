"""Position — the live trade object passed to on_tick() and exit().

pos.vars is a VarsDict: a plain dict subclass that tracks mutations so the engine
knows when to persist a snapshot to the trade_vars table.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


class VarsDict(dict):  # type: ignore[type-arg]
    """Mutable per-trade state bag. Tracks whether it has unsaved changes."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._dirty = False

    def __setitem__(self, key: Any, value: Any) -> None:
        super().__setitem__(key, value)
        self._dirty = True

    def __delitem__(self, key: Any) -> None:
        super().__delitem__(key)
        self._dirty = True

    def mark_clean(self) -> None:
        self._dirty = False


class Position:
    """Read view of the current open trade — passed to on_tick() and exit() hooks.

    The engine populates and updates this on every tick. Strategies read it; they
    must not write to any field except pos.vars.
    """

    def __init__(
        self,
        *,
        trade_id: int,
        side: str,
        qty: int,
        entry_price: float,
        entry_time: datetime,
        mode: str,
        initial_vars: dict | None = None,
    ) -> None:
        self.trade_id = trade_id
        self.side = side            # "LONG" | "SHORT"
        self.qty = qty
        self.entry_price = entry_price
        self.entry_time = entry_time
        self.mode = mode            # "live" | "paper" | "backtest"
        self.ltp: float = entry_price       # updated every tick by the engine
        self.vars: VarsDict = VarsDict(initial_vars or {})

    @property
    def pnl(self) -> float:
        """Live unrealized P&L in ₹ (no brokerage)."""
        if self.side == "LONG":
            return (self.ltp - self.entry_price) * self.qty
        return (self.entry_price - self.ltp) * self.qty

    def update_ltp(self, ltp: float) -> None:
        """Engine calls this on every tick before dispatching hooks."""
        self.ltp = ltp

    def __repr__(self) -> str:
        return (
            f"Position(side={self.side}, qty={self.qty}, entry={self.entry_price:.2f}, "
            f"ltp={self.ltp:.2f}, pnl={self.pnl:.2f})"
        )
