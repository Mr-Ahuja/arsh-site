"""Request/response DTOs for the API routes."""

from __future__ import annotations

from pydantic import BaseModel


class LoginIn(BaseModel):
    username: str
    password: str


class KiteCredsIn(BaseModel):
    api_key: str
    api_secret: str | None = None  # only overwrite when provided


class TelegramIn(BaseModel):
    bot_token: str | None = None  # only overwrite when provided
    chat_id: str | None = None


class TelegramTestIn(BaseModel):
    bot_token: str | None = None  # if provided, use directly (don't require DB entry)
    chat_id: str | None = None
