"""Generic CRUD repository. Per-entity repos subclass and add only entity-specific queries."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    model: type[T]

    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def get(self, id_: Any) -> T | None:
        return await self.s.get(self.model, id_)

    async def list(
        self,
        *,
        where: Any = None,
        order: Any = None,
        page: int = 1,
        size: int = 50,
    ) -> list[T]:
        stmt = select(self.model)
        if where is not None:
            stmt = stmt.where(where)
        if order is not None:
            stmt = stmt.order_by(order)
        stmt = stmt.limit(size).offset((page - 1) * size)
        result = await self.s.execute(stmt)
        return list(result.scalars().all())

    async def create(self, **kw: Any) -> T:
        obj = self.model(**kw)
        self.s.add(obj)
        await self.s.flush()
        return obj

    async def update(self, id_: Any, **kw: Any) -> T | None:
        obj = await self.get(id_)
        if obj is None:
            return None
        for k, v in kw.items():
            setattr(obj, k, v)
        await self.s.flush()
        return obj

    async def delete(self, id_: Any) -> bool:
        obj = await self.get(id_)
        if obj is None:
            return False
        await self.s.delete(obj)
        await self.s.flush()
        return True
