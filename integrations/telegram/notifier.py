"""Notifier interface + a Telegram implementation (email/others later).

Task 01 only needs the interface + a no-op/Telegram send; the engine wires it to the event bus
in later tasks.
"""

from __future__ import annotations

from typing import Protocol

import httpx

from core.config import get_settings
from core.logging import get_logger

log = get_logger(__name__)


class Notifier(Protocol):
    async def send(self, message: str) -> None: ...


class TelegramNotifier:
    async def send(self, message: str) -> None:
        s = get_settings()
        if not s.telegram_bot_token or not s.telegram_chat_id:
            log.info("telegram_skip", reason="not configured", message=message)
            return
        url = f"https://api.telegram.org/bot{s.telegram_bot_token}/sendMessage"
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json={"chat_id": s.telegram_chat_id, "text": message})


def get_notifier() -> Notifier:
    return TelegramNotifier()
