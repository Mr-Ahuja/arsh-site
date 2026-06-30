"""WebSocket endpoint — authenticated live event stream to the browser.

Authentication: the client must pass a valid JWT token as a query-param
?token=<jwt> on the initial connect (cookies can't be set on WS upgrade).

Events published on the bus and forwarded here (kind → payload):
  tick          → {token, ltp, ts, pnl, in_position}
  trade_closed  → {pnl, reason, run_id}
  engine_started / engine_stopped / kill_switch
  order_fill    → {order_ref, state, qty, price}
  position_adopted / alert
"""

from __future__ import annotations

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from core.events import bus
from core.logging import get_logger
from core.security import decode_token

router = APIRouter()
log = get_logger(__name__)


@router.websocket("/ws")
async def ws_endpoint(
    websocket: WebSocket,
    token: str | None = Query(default=None),
) -> None:
    # Validate JWT before accepting the connection
    if not token or not _valid_token(token):
        await websocket.close(code=4001)
        log.warning("ws_auth_rejected")
        return

    await websocket.accept()
    log.info("ws_connected")
    try:
        async for event in bus.subscribe():
            await websocket.send_json({"kind": event.kind, "payload": event.payload})
    except WebSocketDisconnect:
        log.info("ws_disconnect")
    except Exception as exc:  # noqa: BLE001
        log.warning("ws_error", error=str(exc))


def _valid_token(raw: str) -> bool:
    try:
        return bool(decode_token(raw))
    except Exception:  # noqa: BLE001
        return False
