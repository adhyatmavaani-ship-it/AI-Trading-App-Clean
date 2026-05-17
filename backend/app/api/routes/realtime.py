from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect

from app.services.api_key_auth import get_api_key_auth_service
from app.core import metrics
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
    stream_filters = _extract_stream_filters(websocket)
    await manager.connect(websocket, principal.user_id, stream_filters=stream_filters)
    receive_timeout_seconds = max(float(manager.settings.websocket_receive_timeout_seconds), 1.0)
    logger.info(
        "websocket_connection_established",
        extra={
            "event": "websocket_connection_established",
            "context": {
                "user_id": principal.user_id,
                "auth_mode": "api_key",
                "receive_timeout_seconds": receive_timeout_seconds,
                "stream_filters": sorted(stream_filters) if stream_filters else ["all"],
            },
        },
    )
    try:
        while True:
            try:
                message = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=receive_timeout_seconds,
                )
            except TimeoutError:
                logger.info(
                    "websocket_connection_idle",
                    extra={
                        "event": "websocket_connection_idle",
                        "context": {
                            "user_id": principal.user_id,
                            "timeout_seconds": receive_timeout_seconds,
                        },
                    },
                )
                continue
            if message.strip().lower() == "ping":
                await websocket.send_text('{"type":"pong"}')
                continue
            try:
                payload = json.loads(message)
            except json.JSONDecodeError:
                logger.warning(
                    "websocket_control_decode_failed",
                    extra={
                        "event": "websocket_control_decode_failed",
                        "context": {"user_id": principal.user_id},
                    },
                )
                continue
            if not isinstance(payload, dict):
                continue
            if payload.get("type") == "replay_request":
                stream = str(payload.get("stream") or "event")
                metrics.websocket_sequence_gaps.labels(stream=stream).inc()
                response = await manager.replay(websocket, payload)
                await websocket.send_text(json.dumps(response, default=str))
    except WebSocketDisconnect as exc:
        logger.info(
            "websocket_connection_closed",
            extra={
                "event": "websocket_connection_closed",
                "context": {
                    "user_id": principal.user_id,
                    "code": exc.code,
                    "reason": getattr(exc, "reason", "") or "client_disconnect",
                },
            },
        )
        await manager.disconnect(websocket)
    except asyncio.CancelledError:
        logger.info(
            "websocket_connection_cancelled",
            extra={
                "event": "websocket_connection_cancelled",
                "context": {"user_id": principal.user_id},
            },
        )
        await manager.disconnect(websocket)
        raise
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


def _extract_stream_filters(websocket: WebSocket) -> set[str] | None:
    raw = websocket.query_params.get("streams", "")
    streams = {
        item.strip()
        for item in raw.split(",")
        if item.strip()
    }
    allowed = {
        "market_stream",
        "ai_stream",
        "execution_stream",
        "analytics_stream",
        "assistant_stream",
    }
    filtered = streams & allowed
    return filtered or None
