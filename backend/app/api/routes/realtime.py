from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect

from app.services.api_key_auth import get_api_key_auth_service
from app.services.signal_websocket_manager import get_signal_websocket_manager


logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/signals")
async def websocket_signals(websocket: WebSocket) -> None:
    api_key = _extract_api_key(websocket)
    principal = get_api_key_auth_service().authenticate(api_key) if api_key else None
    if principal is None:
        await websocket.close(code=1008, reason="Invalid or missing API key")
        return

    manager = get_signal_websocket_manager()
    await manager.connect(websocket, principal.user_id)
    try:
        while True:
            message = await websocket.receive_text()
            if message.strip().lower() == "ping":
                await websocket.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as exc:  # pragma: no cover
        logger.warning(
            "websocket_connection_failed",
            extra={
                "event": "websocket_connection_failed",
                "context": {
                    "user_id": principal.user_id,
                    "error": str(exc)[:200],
                },
            },
        )
        await manager.disconnect(websocket)


def _extract_api_key(websocket: WebSocket) -> str:
    api_key = (
        websocket.headers.get("authorization", "")
        or websocket.headers.get("x-api-key")
        or websocket.query_params.get("api_key", "")
        or websocket.query_params.get("token", "")
    )
    if api_key.startswith("Bearer "):
        return api_key[7:].strip()
    return api_key.strip()
