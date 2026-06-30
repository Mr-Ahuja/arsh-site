"""StrategyOrder — the lightweight order request returned by entry() / self.buy() / self.sell().

This is NOT the DB Order model. It's an intent object the strategy creates and the
engine runner reads. The runner validates it against risk caps, then hands it to the
broker, which creates the real DB Order row.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class StrategyOrder:
    side: str                       # "BUY" | "SELL"
    qty: int
    order_type: str = "MARKET"      # "MARKET" | "LIMIT"
    price: float | None = None      # required for LIMIT
    product: str = "MIS"            # intraday only in v1
    reason: str = "entry"           # "entry" | "exit" | "squareoff" | "kill_switch"
