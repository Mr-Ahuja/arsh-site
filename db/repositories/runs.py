"""Repository for engine Run rows."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from db.models import Run
from db.repository import BaseRepository


class RunRepository(BaseRepository[Run]):
    model = Run

    async def get_active(self) -> Run | None:
        """Return the most recent run with status='running', or None."""
        stmt = (
            select(Run)
            .where(Run.status == "running")
            .order_by(Run.started_at.desc())
            .limit(1)
        )
        result = await self.s.execute(stmt)
        return result.scalar_one_or_none()

    async def start(self, *, mode: str, strategy: str, params_json: str, started_at: datetime) -> Run:
        return await self.create(
            mode=mode,
            strategy=strategy,
            params_json=params_json,
            started_at=started_at,
            status="running",
        )

    async def finish(self, id_: int, *, status: str, stopped_at: datetime) -> Run | None:
        return await self.update(id_, status=status, stopped_at=stopped_at)
