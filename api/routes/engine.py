"""Engine control API — start, stop, kill-switch, status, and SAFE-mode reconciliation.

All mutation endpoints require:
  - Valid JWT session (current_user)
  - Double-submit CSRF token (require_csrf)

Kill-switch additionally requires the kill_token header for an extra auth layer.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import ValidationError as AppValidationError
from core.schemas import ApiResponse
from core.security import current_user, require_csrf
from db.base import get_session
from engine.runner import create_runner, get_engine_state

router = APIRouter(tags=["engine"])


# ── Request schemas ────────────────────────────────────────────────────────────

class EngineStartIn(BaseModel):
    strategy: str               # "module.ClassName" e.g. "ema_crossover.Strategy"
    mode: str = "paper"         # paper | live | backtest
    params: dict[str, Any] = {}


class ReconcileAdoptIn(BaseModel):
    side: str                   # BUY | SELL
    qty: int
    avg_price: float


# ── Status ─────────────────────────────────────────────────────────────────────

@router.get("/status")
async def engine_status(user: str = Depends(current_user)) -> ApiResponse:
    s = get_engine_state()
    return ApiResponse(data={
        "running": s.running,
        "mode": s.mode,
        "strategy": s.strategy_name,
        "run_id": s.run_id,
        "safe_mode": s.safe_mode,
        "safe_mode_reason": s.safe_mode_reason,
    })


# ── Start ──────────────────────────────────────────────────────────────────────

@router.post("/start")
async def engine_start(
    body: EngineStartIn,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    user: str = Depends(current_user),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse:
    s = get_engine_state()
    if s.running:
        raise AppValidationError("Engine is already running. Stop it first.")
    if body.mode not in ("paper", "live", "backtest"):
        raise AppValidationError(f"Invalid mode: {body.mode!r}")

    runner = await create_runner(
        strategy_name=body.strategy,
        mode=body.mode,
        params=body.params or None,
    )
    await runner.start()

    async def _run_loop():
        """Runs in background — subscribes to ticker events and feeds the runner."""
        from core.events import bus
        try:
            async for event in bus.subscribe():
                if event.kind == "tick":
                    from datetime import datetime

                    from engine.data.types import TickData
                    payload = event.payload
                    tick = TickData(
                        instrument_token=payload["token"],
                        ts=datetime.fromisoformat(payload["ts"]),
                        ltp=payload["ltp"],
                        qty=payload.get("qty", 0),
                        volume=payload.get("volume", 0),
                    )
                    if runner._stopping.is_set():
                        break
                    await runner.on_tick(tick)
                elif event.kind == "candle":
                    from datetime import datetime

                    from engine.data.types import CandleData
                    p = event.payload
                    candle = CandleData(
                        instrument_token=p["token"],
                        timeframe=p["timeframe"],
                        ts=datetime.fromisoformat(p["ts"]),
                        open=p["open"], high=p["high"],
                        low=p["low"], close=p["close"],
                        volume=p["volume"], is_complete=True,
                    )
                    await runner.on_candle(candle)
                elif event.kind in ("engine_stopped", "kill_switch"):
                    break
        except Exception as exc:
            from core.logging import get_logger
            get_logger(__name__).error("runner_loop_error", error=str(exc))

    background_tasks.add_task(_run_loop)
    return ApiResponse(data={"started": True, "run_id": s.run_id, "mode": body.mode})


# ── Stop ───────────────────────────────────────────────────────────────────────

@router.post("/stop")
async def engine_stop(
    user: str = Depends(current_user),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse:
    s = get_engine_state()
    if not s.running or s.runner is None:
        raise AppValidationError("Engine is not running.")
    await s.runner.stop(reason="manual")
    return ApiResponse(data={"stopped": True})


# ── Kill-switch ────────────────────────────────────────────────────────────────

@router.post("/kill")
async def engine_kill(
    user: str = Depends(current_user),
    _csrf: None = Depends(require_csrf),
    x_kill_token: str | None = Header(default=None, alias="X-Kill-Token"),
) -> ApiResponse:
    from core.config import get_settings
    cfg = get_settings()
    if x_kill_token != cfg.kill_token:
        raise HTTPException(status_code=403, detail="Invalid kill token")

    s = get_engine_state()
    if not s.running or s.runner is None:
        raise AppValidationError("Engine is not running.")
    await s.runner.kill()
    return ApiResponse(data={"killed": True})


# ── SAFE-mode reconciliation ───────────────────────────────────────────────────

@router.post("/reconcile/adopt")
async def reconcile_adopt(
    body: ReconcileAdoptIn,
    user: str = Depends(current_user),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse:
    s = get_engine_state()
    if not s.safe_mode or s.runner is None:
        raise AppValidationError("Engine is not in SAFE mode.")
    await s.runner.reconcile_adopt(side=body.side, qty=body.qty, avg_price=body.avg_price)
    return ApiResponse(data={"adopted": True})


@router.post("/reconcile/square-off")
async def reconcile_squareoff(
    user: str = Depends(current_user),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse:
    s = get_engine_state()
    if not s.safe_mode or s.runner is None:
        raise AppValidationError("Engine is not in SAFE mode.")
    await s.runner.reconcile_squareoff()
    return ApiResponse(data={"squared_off": True})


@router.post("/resume")
async def engine_resume(
    user: str = Depends(current_user),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse:
    s = get_engine_state()
    if not s.safe_mode or s.runner is None:
        raise AppValidationError("Engine is not in SAFE mode.")
    await s.runner.reconcile_resume()
    return ApiResponse(data={"resumed": True})


# ── Kite postback webhook (no auth — Kite calls this) ─────────────────────────

@router.post("/postback")
async def kite_postback(data: dict[str, Any]) -> dict:
    """Kite sends order updates here. Forwarded to LiveBroker if running live."""
    s = get_engine_state()
    if s.running and s.mode == "live" and s.runner is not None:
        from engine.brokers.live import LiveBroker
        broker = s.runner._broker
        if isinstance(broker, LiveBroker):
            fill = await broker.handle_postback(data)
            if fill:
                from core.events import Event, bus
                await bus.publish(Event("order_fill", {
                    "order_ref": fill.order_ref,
                    "state": fill.state,
                    "qty": fill.filled_qty,
                    "price": fill.avg_price,
                }))
    return {"status": "ok"}
