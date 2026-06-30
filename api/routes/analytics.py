"""Analytics API — equity curve, metrics, and daily breakdown."""

from __future__ import annotations

from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.schemas import ApiResponse
from core.security import current_user
from db.base import get_session
from db.models import Run, Trade

router = APIRouter(tags=["analytics"])
IST = ZoneInfo("Asia/Kolkata")


def _metrics_from_trades(trades: list[Trade]) -> dict:
    closed = [t for t in trades if t.pnl is not None]
    if not closed:
        return {
            "total_trades": 0, "wins": 0, "losses": 0,
            "win_rate": None, "avg_win": None, "avg_loss": None,
            "profit_factor": None, "total_pnl": 0.0,
            "max_drawdown": 0.0, "largest_win": None, "largest_loss": None,
        }

    pnls = [t.pnl for t in closed]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    gross_profit = sum(wins) if wins else 0.0
    gross_loss = abs(sum(losses)) if losses else 0.0

    # Drawdown from cumulative equity (sorted by exit_at)
    sorted_trades = sorted(closed, key=lambda t: t.exit_at or t.entry_at)
    cum, peak, max_dd = 0.0, 0.0, 0.0
    for t in sorted_trades:
        cum += t.pnl  # type: ignore[operator]
        if cum > peak:
            peak = cum
        dd = peak - cum
        if dd > max_dd:
            max_dd = dd

    return {
        "total_trades": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(closed) * 100, 1),
        "avg_win": round(gross_profit / len(wins), 2) if wins else None,
        "avg_loss": round(-gross_loss / len(losses), 2) if losses else None,
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else None,
        "total_pnl": round(sum(pnls), 2),
        "max_drawdown": round(max_dd, 2),
        "largest_win": round(max(pnls), 2),
        "largest_loss": round(min(pnls), 2),
    }


def _equity_series(trades: list[Trade]) -> list[dict]:
    """Cumulative P&L series sorted by trade exit time."""
    closed = sorted(
        [t for t in trades if t.pnl is not None and t.exit_at is not None],
        key=lambda t: t.exit_at,  # type: ignore[arg-type]
    )
    cum = 0.0
    points = []
    for t in closed:
        cum += t.pnl  # type: ignore[operator]
        exit_ist = t.exit_at.astimezone(IST)  # type: ignore[union-attr]
        points.append({
            "date": exit_ist.strftime("%d %b %H:%M"),
            "pnl": round(cum, 2),
            "trade_pnl": round(t.pnl, 2),  # type: ignore[arg-type]
            "symbol": t.symbol,
        })
    return points


def _daily_series(trades: list[Trade]) -> list[dict]:
    """Per-day P&L totals."""
    closed = [t for t in trades if t.pnl is not None and t.exit_at is not None]
    daily: dict[str, float] = {}
    for t in closed:
        day = t.exit_at.astimezone(IST).strftime("%d %b")  # type: ignore[union-attr]
        daily[day] = round(daily.get(day, 0.0) + t.pnl, 2)  # type: ignore[operator]
    return [{"date": d, "pnl": v} for d, v in daily.items()]


async def _load_trades(
    session: AsyncSession,
    run_id: int | None,
    mode: str | None,
) -> list[Trade]:
    stmt = select(Trade).where(Trade.status == "closed")
    if run_id is not None:
        stmt = stmt.where(Trade.run_id == run_id)
    if mode:
        stmt = stmt.where(Trade.mode == mode)
    stmt = stmt.order_by(Trade.exit_at.asc())
    return list((await session.execute(stmt)).scalars().all())


@router.get("/metrics")
async def get_metrics(
    run_id: int | None = None,
    mode: str | None = None,
    user: str = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    trades = await _load_trades(session, run_id, mode)
    return ApiResponse(data=_metrics_from_trades(trades))


@router.get("/equity")
async def get_equity(
    run_id: int | None = None,
    mode: str | None = None,
    user: str = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    trades = await _load_trades(session, run_id, mode)
    return ApiResponse(data=_equity_series(trades))


@router.get("/daily")
async def get_daily(
    run_id: int | None = None,
    mode: str | None = None,
    user: str = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    trades = await _load_trades(session, run_id, mode)
    return ApiResponse(data=_daily_series(trades))


@router.get("/runs")
async def list_runs(
    mode: str | None = None,
    user: str = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    stmt = select(Run).order_by(Run.started_at.desc()).limit(100)
    if mode:
        stmt = stmt.where(Run.mode == mode)
    runs = (await session.execute(stmt)).scalars().all()
    return ApiResponse(data=[
        {
            "id": r.id,
            "mode": r.mode,
            "strategy": r.strategy.split(".")[-1] if r.strategy else r.strategy,
            "started_at": r.started_at.astimezone(IST).strftime("%d %b %H:%M"),
            "stopped_at": r.stopped_at.astimezone(IST).strftime("%d %b %H:%M") if r.stopped_at else None,
            "status": r.status,
        }
        for r in runs
    ])
