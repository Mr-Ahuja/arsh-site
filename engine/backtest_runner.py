"""Standalone backtest runner — feeds historical candles through the engine offline.

Does NOT touch the live EngineState singleton so it can run in the background
while the paper/live engine is idle.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import select

from core.logging import get_logger
from db.base import async_session
from db.models import Backtest, Run, Trade
from engine.brokers.backtest import BacktestBroker
from engine.data.types import CandleData
from engine.strategy.loader import instantiate, load_strategy
from integrations.kite.historical import fetch_candles

log = get_logger(__name__)


def _compute_metrics(trades: list[Trade]) -> dict:
    closed = [t for t in trades if t.pnl is not None]
    if not closed:
        return {"total_trades": 0, "wins": 0, "losses": 0}

    pnls = [t.pnl for t in closed]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    gross_profit = sum(wins) if wins else 0.0
    gross_loss = abs(sum(losses)) if losses else 0.0
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else None

    # Max drawdown from cumulative P&L series
    cum = 0.0
    peak = 0.0
    max_dd = 0.0
    for p in sorted(pnls, key=lambda _: 0):  # order preserved (entry_at sorted)
        cum += p
        if cum > peak:
            peak = cum
        dd = peak - cum
        if dd > max_dd:
            max_dd = dd

    return {
        "total_trades": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(closed) * 100, 1) if closed else None,
        "avg_win": round(gross_profit / len(wins), 2) if wins else None,
        "avg_loss": round(-gross_loss / len(losses), 2) if losses else None,
        "profit_factor": profit_factor,
        "total_pnl": round(sum(pnls), 2),
        "max_drawdown": round(max_dd, 2),
        "largest_win": round(max(pnls), 2),
        "largest_loss": round(min(pnls), 2),
    }


async def run_backtest(backtest_id: int) -> None:
    """Background task: load config from DB, run, save results."""
    async with async_session() as session:
        bt = await session.get(Backtest, backtest_id)
        if bt is None:
            log.error("backtest_not_found", id=backtest_id)
            return

        try:
            bt.status = "running"
            bt.started_at = datetime.now(UTC)
            await session.commit()

            params = json.loads(bt.params_json or "{}")

            # ── Fetch historical candles ─────────────────────────────────────
            raw_candles = await fetch_candles(
                instrument_token=int(bt.symbol.split(":")[1]) if ":" in bt.symbol else int(bt.symbol),
                from_date=bt.date_from,
                to_date=bt.date_to,
                interval=bt.timeframe,
            )

            if not raw_candles:
                raise RuntimeError("No candles returned from Kite Historical API for this range.")

            # ── Create a fresh Run row ────────────────────────────────────────
            run = Run(
                mode="backtest",
                strategy=bt.strategy,
                params_json=bt.params_json or "{}",
                started_at=datetime.now(UTC),
                status="running",
            )
            session.add(run)
            await session.flush()  # get run.id
            run_id = run.id

            # ── Build minimal engine components ──────────────────────────────
            cls = load_strategy(bt.strategy)
            strategy = instantiate(cls, params_override=params)
            strategy._run_id = run_id
            strategy._mode = "backtest"

            broker = BacktestBroker(run_id=run_id)

            strategy.on_start()
            strategy._reset_session_indicators()
            await broker.start()

            position = None
            trade_id = None

            # ── Feed candles ─────────────────────────────────────────────────
            for raw in raw_candles:
                ts = raw["date"]
                if not isinstance(ts, datetime):
                    ts = datetime.fromisoformat(str(ts))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)

                candle = CandleData(
                    instrument_token=bt.symbol,
                    timeframe=bt.timeframe,
                    ts=ts,
                    open=float(raw["open"]),
                    high=float(raw["high"]),
                    low=float(raw["low"]),
                    close=float(raw["close"]),
                    volume=int(raw["volume"]),
                    is_complete=True,
                )

                strategy._feed_candle(candle)
                fills = await broker.on_candle(candle)

                # Handle fills (simplified — no DB writes during backtest loop)
                for fill in fills:
                    log.debug("backtest_fill", ref=fill.order_ref, state=fill.state)

                # Strategy hooks
                if position is None:
                    order = strategy._call_entry(candle)
                    if order:
                        # Record in DB and open position
                        from engine.strategy.position import Position
                        trade = Trade(
                            run_id=run_id,
                            symbol=str(bt.symbol),
                            instrument_token=0,
                            side=order.side,
                            qty=order.qty,
                            mode="backtest",
                            entry_price=candle.close,
                            entry_at=candle.ts,
                            status="open",
                        )
                        session.add(trade)
                        await session.flush()
                        trade_id = trade.id
                        position = Position(
                            trade_id=trade_id,
                            side=order.side,
                            qty=order.qty,
                            entry_price=candle.close,
                            entry_at=candle.ts,
                        )
                else:
                    position.update_ltp(candle.close)
                    strategy._call_on_tick(candle, position)
                    should_exit = strategy._call_exit(candle, position)

                    # Risk backstop — 15:15 forced exit (check by time)
                    if not should_exit:
                        candle_time = candle.ts.astimezone(UTC)
                        if candle_time.hour >= 15 and candle_time.minute >= 15:
                            should_exit = True

                    if should_exit and trade_id is not None:
                        trade = await session.get(Trade, trade_id)
                        if trade:
                            pnl = (candle.close - position.entry_price) * position.qty
                            if position.side == "SELL":
                                pnl = -pnl
                            trade.exit_price = candle.close
                            trade.exit_at = candle.ts
                            trade.pnl = round(pnl, 2)
                            trade.status = "closed"
                            trade.exit_reason = "strategy"
                        position = None
                        trade_id = None

            # Close any still-open position at last candle
            if position and trade_id:
                last = raw_candles[-1]
                last_price = float(last["close"])
                trade = await session.get(Trade, trade_id)
                if trade:
                    pnl = (last_price - position.entry_price) * position.qty
                    if position.side == "SELL":
                        pnl = -pnl
                    trade.exit_price = last_price
                    trade.exit_at = candle.ts if raw_candles else datetime.now(UTC)
                    trade.pnl = round(pnl, 2)
                    trade.status = "closed"
                    trade.exit_reason = "forced_squareoff"

            run.stopped_at = datetime.now(UTC)
            run.status = "stopped"
            await session.flush()

            # ── Collect trades and metrics ────────────────────────────────────
            result = await session.execute(
                select(Trade).where(Trade.run_id == run_id)
            )
            trades = list(result.scalars().all())
            metrics = _compute_metrics(trades)

            bt.status = "done"
            bt.finished_at = datetime.now(UTC)
            bt.result_json = json.dumps({"run_id": run_id, "metrics": metrics})
            await session.commit()

            log.info("backtest_done", id=backtest_id, run_id=run_id,
                     trades=metrics.get("total_trades"))

        except Exception as exc:
            log.error("backtest_error", id=backtest_id, error=str(exc))
            bt.status = "error"
            bt.result_json = json.dumps({"error": str(exc)})
            await session.commit()
