"""Domain repositories — one per model group. All extend BaseRepository[T]."""

from db.repositories.backtests import BacktestRepository
from db.repositories.candles import CandleRepository
from db.repositories.equity import EquityRepository
from db.repositories.orders import OrderRepository
from db.repositories.runs import RunRepository
from db.repositories.ticks import TickRepository
from db.repositories.trade_vars import TradeVarRepository
from db.repositories.trades import TradeRepository

__all__ = [
    "BacktestRepository",
    "CandleRepository",
    "EquityRepository",
    "OrderRepository",
    "RunRepository",
    "TickRepository",
    "TradeVarRepository",
    "TradeRepository",
]
