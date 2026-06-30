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


async def send_message(bot_token: str, chat_id: str, text: str) -> None:
    """Low-level Telegram send — caller provides credentials."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, json={"chat_id": chat_id, "text": text})
        r.raise_for_status()


class TelegramNotifier:
    async def send(self, message: str) -> None:
        s = get_settings()
        if not s.telegram_bot_token or not s.telegram_chat_id:
            log.info("telegram_skip", reason="not configured", message=message)
            return
        await send_message(s.telegram_bot_token, s.telegram_chat_id, message)


def get_notifier() -> Notifier:
    return TelegramNotifier()
