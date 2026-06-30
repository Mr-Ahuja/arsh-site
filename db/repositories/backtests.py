"""Repository for Backtest run records."""

from __future__ import annotations

from datetime import datetime

from db.models import Backtest
from db.repository import BaseRepository


class BacktestRepository(BaseRepository[Backtest]):
    model = Backtest

    async def recent(self, *, page: int = 1, size: int = 20) -> list[Backtest]:
        """Latest backtest runs for the dashboard list."""
        return await self.list(order=Backtest.id.desc(), page=page, size=size)

    async def start(self, id_: int, *, started_at: datetime) -> Backtest | None:
        return await self.update(id_, status="running", started_at=started_at)

    async def finish(
        self,
        id_: int,
        *,
        finished_at: datetime,
        result_json: str,
        status: str = "done",
    ) -> Backtest | None:
        return await self.update(
            id_,
            status=status,
            finished_at=finished_at,
            result_json=result_json,
        )
