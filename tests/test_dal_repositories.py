"""Tests for Task-02 domain repositories.

Each test gets a clean DB (conftest autouse _clean_state wipes all tables).
We use asyncio.new_event_loop() via _run() from conftest — same pattern as auth tests.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime

import pytest

from db.base import async_session
from db.repositories import (
    BacktestRepository,
    CandleRepository,
    EquityRepository,
    OrderRepository,
    RunRepository,
    TickRepository,
    TradeRepository,
    TradeVarRepository,
)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _now() -> datetime:
    return datetime.now(UTC)


# ─── RunRepository ────────────────────────────────────────────────────────────

class TestRunRepository:
    def test_start_and_get(self):
        async def _go():
            async with async_session() as s:
                repo = RunRepository(s)
                run = await repo.start(
                    mode="paper",
                    strategy="strategies.ema.Strategy",
                    params_json='{"qty": 10}',
                    started_at=_now(),
                )
                await s.commit()
                fetched = await repo.get(run.id)
                assert fetched is not None
                assert fetched.mode == "paper"
                assert fetched.status == "running"
                assert fetched.stopped_at is None
        _run(_go())

    def test_get_active_returns_running(self):
        async def _go():
            async with async_session() as s:
                repo = RunRepository(s)
                run = await repo.start(
                    mode="live", strategy="strategies.ema.Strategy",
                    params_json="{}", started_at=_now(),
                )
                await s.commit()
                active = await repo.get_active()
                assert active is not None
                assert active.id == run.id
        _run(_go())

    def test_get_active_none_when_finished(self):
        async def _go():
            async with async_session() as s:
                repo = RunRepository(s)
                run = await repo.start(
                    mode="paper", strategy="strategies.ema.Strategy",
                    params_json="{}", started_at=_now(),
                )
                await repo.finish(run.id, status="stopped", stopped_at=_now())
                await s.commit()
                active = await repo.get_active()
                assert active is None
        _run(_go())

    def test_finish_updates_status(self):
        async def _go():
            async with async_session() as s:
                repo = RunRepository(s)
                run = await repo.start(
                    mode="live", strategy="strategies.ema.Strategy",
                    params_json="{}", started_at=_now(),
                )
                await repo.finish(run.id, status="halted", stopped_at=_now())
                await s.commit()
                fetched = await repo.get(run.id)
                assert fetched.status == "halted"
                assert fetched.stopped_at is not None
        _run(_go())


# ─── TradeRepository ─────────────────────────────────────────────────────────

class TestTradeRepository:
    def _make_trade_kw(self, run_id: int | None = None) -> dict:
        return dict(
            run_id=run_id,
            symbol="NSE:SBIN",
            instrument_token=779521,
            side="BUY",
            qty=10,
            mode="paper",
            entry_price=500.0,
            entry_at=_now(),
        )

    def test_create_and_get(self):
        async def _go():
            async with async_session() as s:
                repo = TradeRepository(s)
                t = await repo.create(**self._make_trade_kw())
                await s.commit()
                fetched = await repo.get(t.id)
                assert fetched.symbol == "NSE:SBIN"
                assert fetched.status == "open"
                assert fetched.exit_price is None
        _run(_go())

    def test_open_trades_filters_by_run(self):
        async def _go():
            async with async_session() as s:
                rr = RunRepository(s)
                run = await rr.start(mode="paper", strategy="s", params_json="{}", started_at=_now())
                await s.flush()
                repo = TradeRepository(s)
                await repo.create(**self._make_trade_kw(run_id=run.id))
                await repo.create(**self._make_trade_kw(run_id=run.id))
                await repo.create(**self._make_trade_kw(run_id=None))  # different run
                await s.commit()
                open_trades = await repo.open_trades(run.id)
                assert len(open_trades) == 2
                assert all(t.status == "open" for t in open_trades)
        _run(_go())

    def test_close_trade(self):
        async def _go():
            async with async_session() as s:
                repo = TradeRepository(s)
                t = await repo.create(**self._make_trade_kw())
                await s.flush()
                await repo.close(
                    t.id,
                    exit_price=510.0,
                    exit_at=_now(),
                    pnl=100.0,
                    exit_reason="strategy",
                )
                await s.commit()
                fetched = await repo.get(t.id)
                assert fetched.status == "closed"
                assert fetched.pnl == pytest.approx(100.0)
                assert fetched.exit_reason == "strategy"
        _run(_go())

    def test_count_today(self):
        async def _go():
            async with async_session() as s:
                rr = RunRepository(s)
                run = await rr.start(mode="paper", strategy="s", params_json="{}", started_at=_now())
                await s.flush()
                repo = TradeRepository(s)
                for _ in range(3):
                    await repo.create(**self._make_trade_kw(run_id=run.id))
                await s.commit()
                date_str = _now().strftime("%Y-%m-%d")
                count = await repo.count_today(run.id, date_str)
                assert count == 3
        _run(_go())


# ─── OrderRepository ──────────────────────────────────────────────────────────

class TestOrderRepository:
    def _order_kw(self, trade_id=None, run_id=None) -> dict:
        return dict(
            order_ref=str(uuid.uuid4()),
            trade_id=trade_id,
            run_id=run_id,
            symbol="NSE:SBIN",
            side="BUY",
            qty=10,
            order_type="MARKET",
            product="MIS",
            state="CREATED",
            filled_qty=0,
            created_at=_now(),
            updated_at=_now(),
        )

    def test_by_ref_idempotency(self):
        async def _go():
            async with async_session() as s:
                repo = OrderRepository(s)
                ref = str(uuid.uuid4())
                kw = self._order_kw()
                kw["order_ref"] = ref
                o = await repo.create(**kw)
                await s.commit()
                found = await repo.by_ref(ref)
                assert found is not None
                assert found.id == o.id
        _run(_go())

    def test_duplicate_order_ref_raises(self):
        async def _go():
            async with async_session() as s:
                repo = OrderRepository(s)
                ref = str(uuid.uuid4())
                kw = self._order_kw()
                kw["order_ref"] = ref
                await repo.create(**kw)
                await s.commit()
            # Second session — try to insert same ref
            from sqlalchemy.exc import IntegrityError
            with pytest.raises(IntegrityError):
                async with async_session() as s2:
                    repo2 = OrderRepository(s2)
                    kw2 = self._order_kw()
                    kw2["order_ref"] = ref
                    await repo2.create(**kw2)
                    await s2.commit()
        _run(_go())

    def test_pending_for_trade(self):
        async def _go():
            async with async_session() as s:
                repo = OrderRepository(s)
                kw1 = self._order_kw(trade_id=99)
                kw1["state"] = "PENDING"
                kw2 = self._order_kw(trade_id=99)
                kw2["state"] = "COMPLETE"
                await repo.create(**kw1)
                await repo.create(**kw2)
                await s.commit()
                pending = await repo.pending_for_trade(99)
                assert len(pending) == 1
                assert pending[0].state == "PENDING"
        _run(_go())

    def test_transition_state(self):
        async def _go():
            async with async_session() as s:
                repo = OrderRepository(s)
                o = await repo.create(**self._order_kw())
                await s.flush()
                await repo.transition(
                    o.id,
                    state="COMPLETE",
                    filled_qty=10,
                    avg_fill_price=501.5,
                    broker_order_id="KT123456",
                )
                await s.commit()
                fetched = await repo.get(o.id)
                assert fetched.state == "COMPLETE"
                assert fetched.filled_qty == 10
                assert fetched.avg_fill_price == pytest.approx(501.5)
        _run(_go())


# ─── TradeVarRepository ───────────────────────────────────────────────────────

class TestTradeVarRepository:
    def test_latest_returns_most_recent(self):
        async def _go():
            from datetime import timedelta
            async with async_session() as s:
                repo = TradeVarRepository(s)
                t1 = _now()
                t2 = t1 + timedelta(seconds=5)
                await repo.create(trade_id=1, ts=t1, vars_json='{"peak": 500}')
                await repo.create(trade_id=1, ts=t2, vars_json='{"peak": 510}')
                await s.commit()
                latest = await repo.latest(1)
                assert latest is not None
                assert json.loads(latest.vars_json)["peak"] == 510
        _run(_go())

    def test_for_trade_ordered(self):
        async def _go():
            from datetime import timedelta
            async with async_session() as s:
                repo = TradeVarRepository(s)
                base = _now()
                for i in range(3):
                    await repo.create(
                        trade_id=2,
                        ts=base + timedelta(seconds=i),
                        vars_json=json.dumps({"i": i}),
                    )
                await s.commit()
                snapshots = await repo.for_trade(2)
                assert len(snapshots) == 3
                values = [json.loads(s.vars_json)["i"] for s in snapshots]
                assert values == [0, 1, 2]
        _run(_go())


# ─── TickRepository ───────────────────────────────────────────────────────────

class TestTickRepository:
    def _tick_kw(self, token: int = 256265, ltp: float = 200.0) -> dict:
        return dict(
            instrument_token=token,
            ts=_now(),
            ltp=ltp,
            qty=10,
            volume=50000,
            recorded_at=_now(),
        )

    def test_range_returns_ticks_in_window(self):
        async def _go():
            from datetime import timedelta
            base = _now()
            async with async_session() as s:
                repo = TickRepository(s)
                for i in range(5):
                    kw = self._tick_kw(ltp=200.0 + i)
                    kw["ts"] = base + timedelta(seconds=i)
                    await repo.create(**kw)
                await s.commit()
                ticks = await repo.range(
                    256265,
                    base,
                    base + timedelta(seconds=3),
                )
                assert len(ticks) == 4  # seconds 0,1,2,3
        _run(_go())

    def test_latest_returns_newest(self):
        async def _go():
            from datetime import timedelta
            base = _now()
            async with async_session() as s:
                repo = TickRepository(s)
                kw1 = self._tick_kw(ltp=100.0)
                kw1["ts"] = base
                kw2 = self._tick_kw(ltp=105.0)
                kw2["ts"] = base + timedelta(seconds=10)
                await repo.create(**kw1)
                await repo.create(**kw2)
                await s.commit()
                t = await repo.latest(256265)
                assert t is not None
                assert t.ltp == pytest.approx(105.0)
        _run(_go())


# ─── CandleRepository ─────────────────────────────────────────────────────────

class TestCandleRepository:
    def _candle_kw(self, ts: datetime | None = None) -> dict:
        return dict(
            instrument_token=256265,
            timeframe="5minute",
            ts=ts or _now(),
            open=200.0,
            high=205.0,
            low=198.0,
            close=203.0,
            volume=10000,
            source="kite_historical",
        )

    def test_upsert_inserts_then_updates(self):
        async def _go():
            async with async_session() as s:
                repo = CandleRepository(s)
                ts = _now()
                await repo.upsert(**self._candle_kw(ts=ts))
                await s.commit()
            async with async_session() as s:
                repo = CandleRepository(s)
                # Update close via upsert
                kw = self._candle_kw(ts=ts)
                kw["close"] = 210.0
                kw["source"] = "tick_aggregate"
                await repo.upsert(**kw)
                await s.commit()
            async with async_session() as s:
                repo = CandleRepository(s)
                candles = await repo.range(256265, "5minute", ts, ts)
                assert len(candles) == 1
                assert candles[0].close == pytest.approx(210.0)
                assert candles[0].source == "tick_aggregate"
        _run(_go())

    def test_range_filters_correctly(self):
        async def _go():
            from datetime import timedelta
            base = _now()
            async with async_session() as s:
                repo = CandleRepository(s)
                for i in range(5):
                    kw = self._candle_kw(ts=base + timedelta(minutes=5 * i))
                    await repo.upsert(**kw)
                await s.commit()
                candles = await repo.range(
                    256265, "5minute",
                    base,
                    base + timedelta(minutes=10),  # first 3 candles
                )
                assert len(candles) == 3
        _run(_go())


# ─── EquityRepository ────────────────────────────────────────────────────────

class TestEquityRepository:
    def test_for_run_ordered(self):
        async def _go():
            from datetime import timedelta
            base = _now()
            async with async_session() as s:
                repo = EquityRepository(s)
                for i in range(3):
                    await repo.create(
                        run_id=42,
                        ts=base + timedelta(seconds=i),
                        realized_pnl=float(i * 100),
                        unrealized_pnl=0.0,
                        total_pnl=float(i * 100),
                    )
                await s.commit()
                series = await repo.for_run(42)
                assert len(series) == 3
                assert series[-1].realized_pnl == pytest.approx(200.0)
        _run(_go())

    def test_latest_returns_newest(self):
        async def _go():
            from datetime import timedelta
            base = _now()
            async with async_session() as s:
                repo = EquityRepository(s)
                await repo.create(run_id=7, ts=base, realized_pnl=0.0, unrealized_pnl=0.0, total_pnl=0.0)
                await repo.create(run_id=7, ts=base + timedelta(minutes=1), realized_pnl=500.0, unrealized_pnl=0.0, total_pnl=500.0)
                await s.commit()
                latest = await repo.latest(7)
                assert latest.total_pnl == pytest.approx(500.0)
        _run(_go())


# ─── BacktestRepository ───────────────────────────────────────────────────────

class TestBacktestRepository:
    def _bt_kw(self) -> dict:
        return dict(
            strategy="strategies.ema.Strategy",
            symbol="NSE:SBIN",
            timeframe="5minute",
            date_from="2026-01-01",
            date_to="2026-01-31",
            params_json='{"qty": 5}',
        )

    def test_create_defaults(self):
        async def _go():
            async with async_session() as s:
                repo = BacktestRepository(s)
                bt = await repo.create(**self._bt_kw())
                await s.commit()
                fetched = await repo.get(bt.id)
                assert fetched.status == "pending"
                assert fetched.started_at is None
                assert fetched.result_json is None
        _run(_go())

    def test_start_and_finish(self):
        async def _go():
            async with async_session() as s:
                repo = BacktestRepository(s)
                bt = await repo.create(**self._bt_kw())
                await s.flush()
                await repo.start(bt.id, started_at=_now())
                await repo.finish(
                    bt.id,
                    finished_at=_now(),
                    result_json='{"total_pnl": 1200, "trades": 8}',
                )
                await s.commit()
                fetched = await repo.get(bt.id)
                assert fetched.status == "done"
                assert fetched.started_at is not None
                result = json.loads(fetched.result_json)
                assert result["total_pnl"] == 1200
        _run(_go())

    def test_recent_paginates(self):
        async def _go():
            async with async_session() as s:
                repo = BacktestRepository(s)
                for _ in range(5):
                    await repo.create(**self._bt_kw())
                await s.commit()
                page1 = await repo.recent(page=1, size=3)
                page2 = await repo.recent(page=2, size=3)
                assert len(page1) == 3
                assert len(page2) == 2
        _run(_go())
