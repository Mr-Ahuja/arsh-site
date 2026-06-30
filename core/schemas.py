"""One response envelope used by every route; the frontend axios layer unwraps it uniformly."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorBody(BaseModel):
    code: str
    message: str


class ApiResponse(BaseModel, Generic[T]):
    ok: bool = True
    data: T | None = None
    error: ErrorBody | None = None


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int
