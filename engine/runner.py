"""EngineRunner — the main event loop that drives a strategy through one session.

Lifecycle:
  1. start()       — recover state, warm up, subscribe ticker
  2. _run_loop()   — tick-by-tick: indicators → fills → strategy hooks → risk checks
  3. stop()        — graceful square-off, flush, close run in DB
  4. kill()        — emergency: force-flatten immediately (kill-switch)

Mode wiring:
  paper    → PaperBroker  + live KiteTicker
  backtest → BacktestBroker + archived tick replay / OHLC candle feed
  live     → LiveBroker (Task 07) + live KiteTicker

The runner is started once as a FastAPI background task (Task 08).
Only one runner instance runs at a time (enforced by _engine_state singleton).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from core.clock import now_ist
from core.events import Event, bus
from core.logging import get_logger
from engine.brokers.backtest import BacktestBroker
from engine.brokers.base import BrokerBase, FillResult
from engine.brokers.paper import PaperBroker
from engine.data.types import CandleData, TickData
from engine.risk import RiskAction, RiskGuard, RiskState
from engine.strategy.base import BaseStrategy
from engine.strategy.loader import instantiate
from engine.strategy.position import Position

log = get_logger(__name__)

# ── Singleton engine state (checked by API to prevent double-start) ───────────

class EngineState:
    def __init__(self) -> None:
        self.running: bool = False
        self.mode: str | None = None
        self.strategy_name: str | None = None
        self.run_id: int | None = None
        self.safe_mode: bool = False
        self.safe_mode_reason: str | None = None
        self.runner: EngineRunner | None = None

_state = EngineState()


def get_engine_state() -> EngineState:
    return _state


# ── Runner ─────────────────────────────────────────────────────────────────────

class EngineRunner:
    """One strategy, one instrument, one session."""

    def __init__(
        self,
        *,
        strategy: BaseStrategy,
        broker: BrokerBase,
        mode: str,
        run_id: int,
    ) -> None:
        self._strategy = strategy
        self._broker = broker
        self._mode = mode
        self._run_id = run_id
        self._risk_guard = RiskGuard()
        self._risk_state = RiskState()
        self._position: Position | None = None
        self._trade_id: int | None = None
        self._pending_entry_side: str | None = None  # "BUY"/"SELL" of the in-flight entry
        self._stopping = asyncio.Event()

    # ── Public API ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Recover DB state, warm up indicators, subscribe ticker."""
        log.info("runner_start", mode=self._mode, run_id=self._run_id,
                 strategy=self._strategy.__class__.__name__)

        # Inject engine context into strategy
        self._strategy._run_id = self._run_id
        self._strategy._mode = self._mode

        # Recover any open trade from DB
        await self._recover_state()

        # on_start hook — strategy registers indicators here
        self._strategy.on_start()
        self._strategy._reset_session_indicators()

        # Warm up indicators from historical candles
        await self._warm_up_indicators()

        await self._broker.start()
        await bus.publish(Event("engine_started", {
            "mode": self._mode,
            "strategy": self._strategy.__class__.__name__,
            "run_id": self._run_id,
        }))

    async def on_tick(self, tick: TickData) -> None:
        """Main hot path — called by ticker subscriber on every live tick."""
        if self._stopping.is_set():
            return

        strategy = self._strategy

        # 1. Feed tick-mode indicators + track session open price / first-tick flag
        strategy._feed_tick(tick)
        strategy._observe(tick)

        # 2. Process broker fills (paper/live: MARKET fills trigger here)
        fills = await self._broker.on_tick(tick)
        await self._handle_fills(fills, tick)

        # 3. Update unrealised P&L for risk check
        if self._position:
            self._position.update_ltp(tick.ltp)
            self._risk_guard.update_unrealised(self._risk_state, self._position.pnl)

        # 4. Risk backstops
        action = self._risk_guard.check(self._risk_state)
        if action == RiskAction.HALT:
            if self._position:
                await self._square_off(reason="daily_loss")
            await self.stop(reason="daily_loss_halt")
            return
        if action == RiskAction.FORCE_SQUAREOFF:
            if self._position:
                await self._square_off(reason="forced_squareoff")
            await self.stop(reason="forced_squareoff")
            return

        # 5. In SAFE mode: no entries, no strategy hooks for exit
        if _state.safe_mode:
            return

        # 6. Strategy hooks
        if self._position is None:
            # Flat: check entry
            if not await self._broker.has_inflight(self._trade_id):
                order = strategy._call_entry(tick)
                if order:
                    await self._open_trade(order, tick)
        else:
            # In position: update vars, check exit
            strategy._call_on_tick(tick, self._position)
            await self._persist_vars_if_dirty()

            if strategy._call_exit(tick, self._position):
                await self._square_off(reason="strategy")

        # 7. Publish live tick event for WebSocket
        await bus.publish(Event("tick", {
            "token": tick.instrument_token,
            "ltp": tick.ltp,
            "ts": tick.ts.isoformat(),
            "pnl": self._position.pnl if self._position else 0.0,
            "in_position": self._position is not None,
        }))

    async def on_candle(self, candle: CandleData) -> None:
        """Called by candle aggregator on every completed bar."""
        strategy = self._strategy
        strategy._feed_candle(candle)
        # Buffer is managed externally (MultiAggregator feeds RollingBuffer)

        # OHLC backtest: process candle-based fills
        fills = await self._broker.on_candle(candle)
        if fills:
            await self._handle_fills(fills, tick=None)

    async def stop(self, reason: str = "manual") -> None:
        """Graceful shutdown — square off open position, close run in DB."""
        if self._stopping.is_set():
            return
        self._stopping.set()
        log.info("runner_stop", reason=reason, run_id=self._run_id)

        if self._position:
            await self._square_off(reason=reason)

        self._strategy.on_stop()
        await self._broker.stop()
        await self._close_run(reason)
        _state.running = False
        _state.runner = None
        await bus.publish(Event("engine_stopped", {"reason": reason, "run_id": self._run_id}))

    async def kill(self) -> None:
        """Emergency kill-switch — immediately flatten any position."""
        log.warning("kill_switch_triggered", run_id=self._run_id)
        await bus.publish(Event("kill_switch", {"run_id": self._run_id}))
        await self.stop(reason="kill_switch")

    # ── SAFE-mode reconciliation actions ─────────────────────────────────────

    async def reconcile_adopt(self, side: str, qty: int, avg_price: float) -> None:
        """Adopt an externally-created broker position into the engine."""
        if not _state.safe_mode:
            raise RuntimeError("adopt only allowed in SAFE mode")
        from core.clock import now_ist
        self._position = Position(
            trade_id=self._trade_id or -1,
            side="LONG" if side == "BUY" else "SHORT",
            qty=qty,
            entry_price=avg_price,
            entry_time=now_ist(),
            mode=self._mode,
        )
        _state.safe_mode = False
        _state.safe_mode_reason = None
        log.info("position_adopted", side=side, qty=qty, avg_price=avg_price)
        await bus.publish(Event("position_adopted", {"side": side, "qty": qty}))

    async def reconcile_squareoff(self) -> None:
        """Square off an unexpected broker position from SAFE mode."""
        if not _state.safe_mode:
            raise RuntimeError("squareoff only allowed in SAFE mode")
        if self._position:
            await self._square_off(reason="manual")
        _state.safe_mode = False
        _state.safe_mode_reason = None

    async def reconcile_resume(self) -> None:
        """Exit SAFE mode (only when flat-flat or after adopt)."""
        if _state.safe_mode and self._position is not None:
            raise RuntimeError("resolve the position mismatch before resuming")
        _state.safe_mode = False
        _state.safe_mode_reason = None
        log.info("engine_resumed")

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _recover_state(self) -> None:
        """Load any open trade + pos.vars from the last run (restart recovery)."""
        from db.base import async_session
        from db.repositories import TradeRepository, TradeVarRepository

        async with async_session() as s:
            trade_repo = TradeRepository(s)
            var_repo = TradeVarRepository(s)
            open_trades = await trade_repo.open_trades(self._run_id)
            if not open_trades:
                return
            trade = open_trades[0]
            self._trade_id = trade.id
            latest_vars = await var_repo.latest(trade.id)
            vars_dict = json.loads(latest_vars.vars_json) if latest_vars else {}
            self._position = Position(
                trade_id=trade.id,
                side="LONG" if trade.side == "BUY" else "SHORT",
                qty=trade.qty,
                entry_price=trade.entry_price,
                entry_time=trade.entry_at,
                mode=trade.mode,
                initial_vars=vars_dict,
            )
            log.info("state_recovered", trade_id=trade.id, side=trade.side)

    async def _warm_up_indicators(self) -> None:
        """Pre-fill indicators from historical candles so they start with valid values."""
        if not hasattr(self._strategy, "_buffer"):
            return
        buf = self._strategy._buffer
        candles = buf.last_n_candles(500)
        for c in candles:
            self._strategy._feed_candle(c)
        log.info("indicators_warmed_up", candles_fed=len(candles))

    async def _open_trade(self, order: StrategyOrder, tick: TickData) -> None:  # noqa: F821
        from db.base import async_session
        from db.repositories import TradeRepository

        symbol = self._strategy.instrument
        token = tick.instrument_token
        self._pending_entry_side = order.side  # remember BUY/SELL for the fill → LONG/SHORT map

        # Persist trade first (CREATED order will link back)
        async with async_session() as s:
            repo = TradeRepository(s)
            trade = await repo.create(
                run_id=self._run_id,
                symbol=symbol,
                instrument_token=token,
                side=order.side,
                qty=order.qty,
                mode=self._mode,
                entry_price=tick.ltp,   # approximate — overwritten on fill
                entry_at=now_ist(),
                status="open",
            )
            self._trade_id = trade.id

        await self._broker.place_order(
            order,
            symbol=symbol,
            instrument_token=token,
            run_id=self._run_id,
            trade_id=self._trade_id,
        )
        log.info("entry_order_placed", trade_id=self._trade_id, side=order.side)

    async def _square_off(self, reason: str) -> None:
        from engine.strategy.order import StrategyOrder

        if self._position is None:
            return
        pos = self._position
        exit_side = "SELL" if pos.side == "LONG" else "BUY"
        so = StrategyOrder(side=exit_side, qty=pos.qty, reason=reason)
        await self._broker.place_order(
            so,
            symbol=self._strategy.instrument,
            instrument_token=0,  # runner has the real token in context
            run_id=self._run_id,
            trade_id=self._trade_id,
        )
        log.info("exit_order_placed", reason=reason, trade_id=self._trade_id)

    async def _handle_fills(self, fills: list[FillResult], tick: TickData | None) -> None:
        from db.base import async_session
        from db.repositories import TradeRepository

        for fill in fills:
            if fill.state not in ("COMPLETE", "PARTIAL"):
                log.warning("order_not_filled", state=fill.state, ref=fill.order_ref)
                continue

            if self._position is None:
                # Entry fill → create position
                async with async_session() as s:
                    repo = TradeRepository(s)
                    if self._trade_id:
                        await repo.update(self._trade_id, entry_price=fill.avg_price)
                self._position = Position(
                    trade_id=self._trade_id or -1,
                    side="LONG" if self._pending_entry_side == "BUY" else "SHORT",
                    qty=fill.filled_qty,
                    entry_price=fill.avg_price,
                    entry_time=fill.ts,
                    mode=self._mode,
                )
            else:
                # Exit fill → close position
                pnl = self._position.pnl
                exit_reason = "strategy"
                async with async_session() as s:
                    repo = TradeRepository(s)
                    await repo.close(
                        self._trade_id,
                        exit_price=fill.avg_price,
                        exit_at=fill.ts,
                        pnl=pnl,
                        exit_reason=exit_reason,
                    )
                self._risk_guard.record_closed_trade(self._risk_state, pnl)
                self._position = None
                self._trade_id = None
                self._pending_entry_side = None

                await bus.publish(Event("trade_closed", {
                    "pnl": round(pnl, 2),
                    "reason": exit_reason,
                    "run_id": self._run_id,
                }))

    async def _persist_vars_if_dirty(self) -> None:
        if self._position is None or not self._position.vars._dirty:
            return
        from db.base import async_session
        from db.repositories import TradeVarRepository

        self._position.vars.mark_clean()
        snap = dict(self._position.vars)
        async with async_session() as s:
            repo = TradeVarRepository(s)
            await repo.create(
                trade_id=self._trade_id,
                ts=now_ist(),
                vars_json=json.dumps(snap),
            )

    async def _close_run(self, reason: str) -> None:
        from db.base import async_session
        from db.repositories import RunRepository

        async with async_session() as s:
            repo = RunRepository(s)
            status = "stopped" if reason in ("manual", "forced_squareoff") else "halted"
            await repo.finish(self._run_id, status=status)


# ── Factory ───────────────────────────────────────────────────────────────────

async def create_runner(
    strategy_name: str,
    mode: str,
    params: dict[str, Any] | None = None,
) -> EngineRunner:
    """Load strategy, create run in DB, wire broker, return runner ready to start()."""
    from db.base import async_session
    from db.repositories import RunRepository
    from engine.strategy.loader import load_strategy

    if _state.running:
        raise RuntimeError("Engine already running. Stop it first.")

    cls = load_strategy(strategy_name)
    strategy = instantiate(cls, params_override=params)

    async with async_session() as s:
        repo = RunRepository(s)
        run = await repo.start(
            mode=mode,
            strategy=strategy_name,
            params_json=json.dumps(params or {}),
        )

    broker: BrokerBase
    if mode == "backtest":
        broker = BacktestBroker()
    else:
        broker = PaperBroker()   # paper and live share paper fills; live adds Kite REST

    runner = EngineRunner(strategy=strategy, broker=broker, mode=mode, run_id=run.id)

    _state.running = True
    _state.mode = mode
    _state.strategy_name = strategy_name
    _state.run_id = run.id
    _state.safe_mode = False
    _state.runner = runner
    return runner
