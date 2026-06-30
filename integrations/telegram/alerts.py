"""Telegram alert subscriber — subscribes to the event bus and sends alerts.

Started as a background task at app startup (wired in api/app.py lifespan).
Sends formatted messages to Telegram for key engine events only:
  engine_started, engine_stopped, kill_switch, trade_closed, alert
"""

from __future__ import annotations

import asyncio

from core.events import bus
from core.logging import get_logger
from integrations.telegram.notifier import TelegramNotifier

log = get_logger(__name__)
_notifier = TelegramNotifier()


async def run_alert_subscriber() -> None:
    """Long-running coroutine — subscribe to bus and forward alert-worthy events."""
    log.info("telegram_alert_subscriber_started")
    try:
        async for event in bus.subscribe():
            msg = _format(event.kind, event.payload)
            if msg:
                try:
                    await _notifier.send(msg)
                except Exception as exc:  # noqa: BLE001
                    log.warning("telegram_send_error", error=str(exc))
    except asyncio.CancelledError:
        log.info("telegram_alert_subscriber_stopped")


def _format(kind: str, payload: dict) -> str | None:
    if kind == "engine_started":
        return (
            f"Engine started\n"
            f"Mode: {payload.get('mode')}\n"
            f"Strategy: {payload.get('strategy')}\n"
            f"Run #{payload.get('run_id')}"
        )
    if kind == "engine_stopped":
        return f"Engine stopped — reason: {payload.get('reason')}"
    if kind == "kill_switch":
        return f"KILL SWITCH triggered (run #{payload.get('run_id')})"
    if kind == "trade_closed":
        pnl = payload.get("pnl", 0)
        sign = "+" if pnl >= 0 else ""
        return f"Trade closed — P&L: {sign}{pnl:.2f} INR | Reason: {payload.get('reason')}"
    if kind == "alert":
        return f"Alert: {payload.get('message', '(no message)')}"
    return None  # tick / position events are not Telegram-worthy
