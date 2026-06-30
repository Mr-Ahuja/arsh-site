"""Risk backstops — engine-level guardrails that operate under strategy logic.

Two hard stops enforced by the runner on every tick:
  1. Daily-loss kill:   realised + unrealised P&L <= -max_daily_loss → HALT
  2. Forced square-off: IST time >= force_squareoff_time → exit open position

The runner calls RiskGuard.check() and acts on the returned RiskAction.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from enum import Enum, auto

from core.clock import now_ist
from core.config import get_settings
from core.logging import get_logger

log = get_logger(__name__)


class RiskAction(Enum):
    NONE = auto()
    FORCE_SQUAREOFF = auto()   # open position must be closed immediately
    HALT = auto()              # daily loss exceeded; halt all new entries too


@dataclass
class RiskState:
    """Mutable snapshot of today's risk metrics — updated by the runner."""

    realised_pnl: float = 0.0       # sum of closed trades' P&L today
    unrealised_pnl: float = 0.0     # current open trade's live P&L
    daily_loss_halted: bool = False  # latched True once limit is breached
    squareoff_fired: bool = False    # latched True once forced square-off fires

    @property
    def net_pnl(self) -> float:
        return self.realised_pnl + self.unrealised_pnl


class RiskGuard:
    """Stateless evaluator — all state is in RiskState (passed by runner)."""

    def __init__(self) -> None:
        cfg = get_settings()
        self._max_daily_loss = cfg.max_daily_loss
        # Parse "HH:MM" into a time object
        h, m = cfg.force_squareoff_time.split(":")
        self._squareoff_time = time(int(h), int(m))

    def check(self, state: RiskState) -> RiskAction:
        """Called every tick. Returns the most severe action required (if any)."""

        # Daily loss — checked first; once halted, always halted for the session
        if not state.daily_loss_halted and state.net_pnl <= -self._max_daily_loss:
            state.daily_loss_halted = True
            log.error(
                "risk_daily_loss_halt",
                net_pnl=round(state.net_pnl, 2),
                limit=self._max_daily_loss,
            )
            return RiskAction.HALT

        if state.daily_loss_halted:
            return RiskAction.HALT

        # Forced square-off at end of session
        if not state.squareoff_fired:
            ist_now = now_ist().time().replace(tzinfo=None)
            if ist_now >= self._squareoff_time:
                state.squareoff_fired = True
                log.warning(
                    "risk_force_squareoff",
                    time=str(ist_now),
                    limit=str(self._squareoff_time),
                )
                return RiskAction.FORCE_SQUAREOFF

        return RiskAction.NONE

    def update_unrealised(self, state: RiskState, pnl: float) -> None:
        state.unrealised_pnl = pnl

    def record_closed_trade(self, state: RiskState, pnl: float) -> None:
        state.realised_pnl += pnl
        state.unrealised_pnl = 0.0
