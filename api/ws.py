"""WebSocket endpoint stub — bridges core.events to the browser (live cockpit in Task 09).

Task 01 only wires the plumbing: authenticated connect + echo of bus events.
"""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.events import bus
from core.logging import get_logger

router = APIRouter()
log = get_logger(__name__)


@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        async for event in bus.subscribe():
            await websocket.send_json({"kind": event.kind, "payload": event.payload})
    except WebSocketDisconnect:
        log.info("ws_disconnect")
