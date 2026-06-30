"""Backtest API — submit, poll, and retrieve results."""

from __future__ import annotations

import json
from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import ValidationError as AppValidationError
from core.schemas import ApiResponse
from core.security import current_user, require_csrf
from db.base import get_session
from db.models import Backtest

router = APIRouter(tags=["backtest"])
IST = ZoneInfo("Asia/Kolkata")


class BacktestIn(BaseModel):
    strategy: str           # "module.ClassName"
    symbol: str             # instrument_token as string (e.g. "256265")
    timeframe: str          # minute | 5minute | 15minute | 60minute | day
    date_from: str          # YYYY-MM-DD
    date_to: str            # YYYY-MM-DD
    params: dict = {}


@router.post("")
async def submit_backtest(
    body: BacktestIn,
    background_tasks: BackgroundTasks,
    user: str = Depends(current_user),
    _csrf: None = Depends(require_csrf),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    valid_intervals = {"minute", "3minute", "5minute", "10minute", "15minute",
                       "30minute", "60minute", "day"}
    if body.timeframe not in valid_intervals:
        raise AppValidationError(f"Invalid timeframe: {body.timeframe!r}")

    bt = Backtest(
        strategy=body.strategy,
        symbol=body.symbol,
        timeframe=body.timeframe,
        date_from=body.date_from,
        date_to=body.date_to,
        params_json=json.dumps(body.params),
        status="pending",
    )
    session.add(bt)
    await session.flush()
    bt_id = bt.id
    await session.commit()

    from engine.backtest_runner import run_backtest
    background_tasks.add_task(run_backtest, bt_id)

    return ApiResponse(data={"id": bt_id, "status": "pending"})


@router.get("")
async def list_backtests(
    user: str = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    stmt = select(Backtest).order_by(Backtest.id.desc()).limit(50)
    rows = (await session.execute(stmt)).scalars().all()
    return ApiResponse(data=[_bt_row(r) for r in rows])


@router.get("/{bt_id}")
async def get_backtest(
    bt_id: int,
    user: str = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    bt = await session.get(Backtest, bt_id)
    if bt is None:
        raise AppValidationError(f"Backtest {bt_id} not found.")
    return ApiResponse(data=_bt_row(bt, full=True))


def _bt_row(bt: Backtest, *, full: bool = False) -> dict:
    result = json.loads(bt.result_json) if bt.result_json else None
    row: dict = {
        "id": bt.id,
        "strategy": bt.strategy.split(".")[-1] if bt.strategy else bt.strategy,
        "strategy_full": bt.strategy,
        "symbol": bt.symbol,
        "timeframe": bt.timeframe,
        "date_from": bt.date_from,
        "date_to": bt.date_to,
        "status": bt.status,
        "started_at": bt.started_at.astimezone(IST).isoformat() if bt.started_at else None,
        "finished_at": bt.finished_at.astimezone(IST).isoformat() if bt.finished_at else None,
    }
    if full and result:
        row["result"] = result
    elif result:
        row["run_id"] = result.get("run_id")
        row["metrics"] = result.get("metrics")
        row["error"] = result.get("error")
    return row
