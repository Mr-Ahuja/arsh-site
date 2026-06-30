"""SQLAlchemy models. Task 01 tables only: kite_session, events, settings."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class KiteSession(Base):
    """The day's access token (encrypted at rest)."""

    __tablename__ = "kite_session"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64))
    access_token_enc: Mapped[str] = mapped_column(Text)
    valid_for_date: Mapped[str] = mapped_column(String(10))  # YYYY-MM-DD (IST)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Event(Base):
    """Audit log."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    level: Mapped[str] = mapped_column(String(16))
    kind: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(Text)


class Setting(Base):
    """Encrypted key-value config (Kite api_key/secret, ...)."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value_enc: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
