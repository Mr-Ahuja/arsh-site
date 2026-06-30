"""Trade history API — filterable, paginated, and CSV-exportable."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.schemas import ApiResponse
from core.security import current_user
from db.base import get_session
from db.models import Run, Trade

router = APIRouter(tags=["history"])
IST = ZoneInfo("Asia/Kolkata")


def _build_stmt(
    *,
    mode: str | None,
    status: str | None,
    exit_reason: str | None,
    date_from: str | None,
    date_to: str | None,
    symbol: str | None,
    strategy: str | None,
):
    stmt = select(Trade, Run.strategy.label("run_strategy")).outerjoin(
        Run, Trade.run_id == Run.id
    )
    if mode:
        stmt = stmt.where(Trade.mode == mode)
    if status:
        stmt = stmt.where(Trade.status == status)
    if exit_reason:
        stmt = stmt.where(Trade.exit_reason == exit_reason)
    if symbol:
        stmt = stmt.where(Trade.symbol.ilike(f"%{symbol}%"))
    if strategy:
        stmt = stmt.where(Run.strategy.ilike(f"%{strategy}%"))
    if date_from:
        dt = datetime.fromisoformat(date_from).replace(tzinfo=IST)
        stmt = stmt.where(Trade.entry_at >= dt)
    if date_to:
        dt = datetime.fromisoformat(date_to).replace(tzinfo=IST) + timedelta(days=1)
        stmt = stmt.where(Trade.entry_at < dt)
    return stmt.order_by(Trade.entry_at.desc())


def _row_dict(trade: Trade, run_strategy: str | None) -> dict:
    duration_s: int | None = None
    if trade.entry_at and trade.exit_at:
        duration_s = int((trade.exit_at - trade.entry_at).total_seconds())

    strat_name = (run_strategy or "").split(".")[-1] if run_strategy else None

    return {
        "id": trade.id,
        "run_id": trade.run_id,
        "symbol": trade.symbol,
        "side": trade.side,
        "qty": trade.qty,
        "mode": trade.mode,
        "strategy": strat_name,
        "entry_price": trade.entry_price,
        "entry_at": trade.entry_at.astimezone(IST).isoformat() if trade.entry_at else None,
        "exit_price": trade.exit_price,
        "exit_at": trade.exit_at.astimezone(IST).isoformat() if trade.exit_at else None,
        "pnl": trade.pnl,
        "status": trade.status,
        "exit_reason": trade.exit_reason,
        "duration_s": duration_s,
    }


@router.get("/trades")
async def list_trades(
    # filters
    mode: str | None = None,
    status: str | None = None,
    exit_reason: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    symbol: str | None = None,
    strategy: str | None = None,
    # pagination
    page: int = 1,
    limit: int = 50,
    # format
    format: str | None = None,  # noqa: A002
    user: str = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    limit = min(max(limit, 1), 200)
    page = max(page, 1)

    base_stmt = _build_stmt(
        mode=mode, status=status, exit_reason=exit_reason,
        date_from=date_from, date_to=date_to,
        symbol=symbol, strategy=strategy,
    )

    # ── CSV download ──────────────────────────────────────────────────────────
    if format == "csv":
        result = await session.execute(base_stmt)
        rows = result.all()
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "ID", "Symbol", "Side", "Qty", "Mode", "Strategy",
            "Entry Price", "Entry At (IST)", "Exit Price", "Exit At (IST)",
            "P&L", "Duration (s)", "Status", "Exit Reason", "Run ID",
        ])
        for trade, run_strategy in rows:
            d = _row_dict(trade, run_strategy)
            writer.writerow([
                d["id"], d["symbol"], d["side"], d["qty"], d["mode"], d["strategy"] or "",
                d["entry_price"], d["entry_at"] or "", d["exit_price"] or "", d["exit_at"] or "",
                d["pnl"] if d["pnl"] is not None else "",
                d["duration_s"] if d["duration_s"] is not None else "",
                d["status"], d["exit_reason"] or "", d["run_id"] or "",
            ])
        buf.seek(0)
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=trades.csv"},
        )

    # ── Count for pagination ──────────────────────────────────────────────────
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total: int = (await session.execute(count_stmt)).scalar_one()

    # ── Paginated data ────────────────────────────────────────────────────────
    page_stmt = base_stmt.offset((page - 1) * limit).limit(limit)
    result = await session.execute(page_stmt)
    rows = result.all()

    trades_out = [_row_dict(t, rs) for t, rs in rows]

    # ── Per-page summary (full result, not just this page) ────────────────────
    closed = [d for d in trades_out if d["pnl"] is not None]
    wins = [d for d in closed if (d["pnl"] or 0) > 0]
    total_pnl = sum((d["pnl"] or 0) for d in closed)

    return ApiResponse(data={
        "trades": trades_out,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": max(1, (total + limit - 1) // limit),
        "summary": {
            "total": total,
            "wins": len(wins),
            "losses": len(closed) - len(wins),
            "win_rate": round(len(wins) / len(closed) * 100, 1) if closed else None,
            "total_pnl": round(total_pnl, 2) if closed else None,
        },
    })
