"""SQLAlchemy models — all tables for the trade engine."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base

# ── Task 01: auth & config ────────────────────────────────────────────────────

class KiteSession(Base):
    """The day's access token (encrypted at rest)."""

    __tablename__ = "kite_session"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64))
    access_token_enc: Mapped[str] = mapped_column(Text)
    valid_for_date: Mapped[str] = mapped_column(String(10))  # YYYY-MM-DD (IST)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Event(Base):
    """Audit/system log."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    level: Mapped[str] = mapped_column(String(16))
    kind: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(Text)


class Setting(Base):
    """Encrypted key-value config (Kite api_key/secret, Telegram token, …)."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value_enc: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


# ── Task 02: engine runs & trades ────────────────────────────────────────────

class Run(Base):
    """One row per engine run (live / paper / backtest session)."""

    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    mode: Mapped[str] = mapped_column(String(16))          # live | paper | backtest
    strategy: Mapped[str] = mapped_column(String(128))     # module.ClassName
    params_json: Mapped[str] = mapped_column(Text, default="{}")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="running")
    # running | stopped | halted | error


class Trade(Base):
    """One row per completed or open intraday trade."""

    __tablename__ = "trades"
    __table_args__ = (
        Index("ix_trades_run_status", "run_id", "status"),
        Index("ix_trades_entry_at", "entry_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)   # FK → runs.id
    symbol: Mapped[str] = mapped_column(String(32))                       # "NSE:SBIN"
    instrument_token: Mapped[int] = mapped_column(Integer)
    side: Mapped[str] = mapped_column(String(4))                          # BUY | SELL
    qty: Mapped[int] = mapped_column(Integer)
    mode: Mapped[str] = mapped_column(String(16))                         # live | paper | backtest
    entry_price: Mapped[float] = mapped_column(Float)
    entry_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="open")       # open | closed | cancelled
    exit_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # strategy | forced_squareoff | daily_loss | kill_switch | error | manual


class Order(Base):
    """Every order placed by the engine, with full state-machine history."""

    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_trade", "trade_id"),
        Index("ix_orders_run", "run_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_ref: Mapped[str] = mapped_column(String(36), unique=True)       # UUID4 — idempotency key
    trade_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # FK → trades.id
    run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)    # FK → runs.id
    symbol: Mapped[str] = mapped_column(String(32))
    side: Mapped[str] = mapped_column(String(4))                          # BUY | SELL
    qty: Mapped[int] = mapped_column(Integer)
    order_type: Mapped[str] = mapped_column(String(8), default="MARKET")  # MARKET | LIMIT
    price: Mapped[float | None] = mapped_column(Float, nullable=True)     # LIMIT price
    product: Mapped[str] = mapped_column(String(8), default="MIS")
    state: Mapped[str] = mapped_column(String(16), default="CREATED")
    # CREATED | PENDING | OPEN | COMPLETE | PARTIAL | REJECTED | CANCELLED
    broker_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    filled_qty: Mapped[int] = mapped_column(Integer, default=0)
    avg_fill_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(32), nullable=True) # entry | exit | squareoff
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TradeVar(Base):
    """Periodic snapshots of pos.vars for a trade (peak, cutoff, counters, …)."""

    __tablename__ = "trade_vars"
    __table_args__ = (Index("ix_trade_vars_trade_ts", "trade_id", "ts"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    trade_id: Mapped[int] = mapped_column(Integer)     # FK → trades.id
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    vars_json: Mapped[str] = mapped_column(Text)       # JSON dict snapshot


# ── Task 02: market data ──────────────────────────────────────────────────────

class Tick(Base):
    """Recorded tick archive — the raw backtest replay dataset."""

    __tablename__ = "ticks"
    __table_args__ = (Index("ix_ticks_token_ts", "instrument_token", "ts"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_token: Mapped[int] = mapped_column(Integer)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))          # exchange timestamp
    ltp: Mapped[float] = mapped_column(Float)
    qty: Mapped[int] = mapped_column(Integer)                              # last traded qty
    volume: Mapped[int] = mapped_column(Integer)                           # cumulative day volume
    bid: Mapped[float | None] = mapped_column(Float, nullable=True)
    ask: Mapped[float | None] = mapped_column(Float, nullable=True)
    depth_json: Mapped[str | None] = mapped_column(Text, nullable=True)   # 5-level depth (full mode)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True)) # wall-clock insert time


class Candle(Base):
    """OHLCV cache — from Kite Historical API or tick aggregator."""

    __tablename__ = "candles"
    __table_args__ = (
        UniqueConstraint("instrument_token", "timeframe", "ts", name="uq_candle"),
        Index("ix_candles_token_tf_ts", "instrument_token", "timeframe", "ts"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_token: Mapped[int] = mapped_column(Integer)
    timeframe: Mapped[str] = mapped_column(String(16))     # minute | 5minute | 15minute | …
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # candle open time
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(24))        # kite_historical | tick_aggregate


# ── Task 02: analytics & backtests ───────────────────────────────────────────

class Equity(Base):
    """P&L time series — one row per engine tick or periodic flush."""

    __tablename__ = "equity"
    __table_args__ = (Index("ix_equity_run_ts", "run_id", "ts"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # FK → runs.id
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    total_pnl: Mapped[float] = mapped_column(Float, default=0.0)        # realized + unrealized


class Backtest(Base):
    """Backtest run — config, status, and result summary."""

    __tablename__ = "backtests"

    id: Mapped[int] = mapped_column(primary_key=True)
    strategy: Mapped[str] = mapped_column(String(128))
    symbol: Mapped[str] = mapped_column(String(32))
    timeframe: Mapped[str] = mapped_column(String(16))
    date_from: Mapped[str] = mapped_column(String(10))   # YYYY-MM-DD
    date_to: Mapped[str] = mapped_column(String(10))
    params_json: Mapped[str] = mapped_column(Text, default="{}")
    data_source: Mapped[str] = mapped_column(String(24), default="ohlc")
    # ohlc | tick_replay
    status: Mapped[str] = mapped_column(String(16), default="pending")
    # pending | running | done | error
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # trades + metrics


# ── Instruments buffer (searchable picker) ────────────────────────────────────

class Instrument(Base):
    """Buffered Kite equity instruments (NSE/BSE) for the searchable picker.

    Refreshed from Kite once per day; wiped + reloaded on each sync.
    """

    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_token: Mapped[int] = mapped_column(Integer, index=True)
    exchange: Mapped[str] = mapped_column(String(8))          # NSE | BSE
    tradingsymbol: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    synced_on: Mapped[str] = mapped_column(String(10))        # YYYY-MM-DD of last sync

    __table_args__ = (
        UniqueConstraint("exchange", "tradingsymbol", name="uq_instrument_exch_symbol"),
        Index("ix_instrument_search", "exchange", "tradingsymbol"),
    )
