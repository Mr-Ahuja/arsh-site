"""engine.strategy — strategy framework (Task 04).

Public surface:
    BaseStrategy   — subclass this to write a strategy
    Position       — pos object passed to on_tick / exit
    StrategyOrder  — order request returned by entry()
    EMA, SMA, RSI, ATR, VWAP  — built-in indicators
    load_strategy, discover_strategies, instantiate  — loader API
"""

from engine.strategy.base import BaseStrategy, StrategyError
from engine.strategy.indicators import ATR, EMA, RSI, SMA, VWAP, Indicator
from engine.strategy.loader import (
    StrategyLoadError,
    discover_strategies,
    instantiate,
    load_strategy,
)
from engine.strategy.order import StrategyOrder
from engine.strategy.position import Position, VarsDict

__all__ = [
    "ATR",
    "BaseStrategy",
    "EMA",
    "Indicator",
    "Position",
    "RSI",
    "SMA",
    "StrategyError",
    "StrategyLoadError",
    "StrategyOrder",
    "VWAP",
    "VarsDict",
    "discover_strategies",
    "instantiate",
    "load_strategy",
]
