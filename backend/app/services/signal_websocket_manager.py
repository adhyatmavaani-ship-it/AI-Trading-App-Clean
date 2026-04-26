from __future__ import annotations

import asyncio
import json
import logging
import threading
from functools import lru_cache

from fastapi import WebSocket
from redis import Redis
from starlette.websockets import WebSocketDisconnect

from app.core.config import Settings, get_settings


logger = logging.getLogger(__name__)


class SignalWebSocketManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._connections: dict[WebSocket, str] = {}
        self._lock = asyncio.Lock()
        self._listener_thread: threading.Thread | None = None
        self._listener_stop = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[websocket] = user_id

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.pop(websocket, None)

    async def broadcast(self, payload: dict) -> None:
        message = json.dumps(payload, default=str)
        async with self._lock:
            recipients = list(self._connections.keys())

        stale_connections: list[WebSocket] = []
        for websocket in recipients:
            try:
                await websocket.send_text(message)
            except (WebSocketDisconnect, RuntimeError):
                stale_connections.append(websocket)
            except Exception as exc:  # pragma: no cover
                logger.warning(
                    "websocket_broadcast_failed",
                    extra={
                        "event": "websocket_broadcast_failed",
                        "context": {"error": str(exc)[:200]},
                    },
                )
                stale_connections.append(websocket)

        for websocket in stale_connections:
            await self.disconnect(websocket)

    async def start(self) -> None:
        if not self.settings.websocket_listener_enabled:
            return
        if self._listener_thread is not None and self._listener_thread.is_alive():
            return
        self._loop = asyncio.get_running_loop()
        self._listener_stop.clear()
        self._listener_thread = threading.Thread(
            target=self._listen_for_signals,
            name="signal-websocket-listener",
            daemon=True,
        )
        self._listener_thread.start()

    async def stop(self) -> None:
        self._listener_stop.set()
        if self._listener_thread is not None and self._listener_thread.is_alive():
            await asyncio.to_thread(self._listener_thread.join, 2.0)
        self._listener_thread = None

    def _listen_for_signals(self) -> None:
        reconnect_delay = max(float(self.settings.websocket_redis_reconnect_seconds), 0.1)
        while not self._listener_stop.is_set():
            redis_client: Redis | None = None
            pubsub = None
            try:
                redis_client = Redis.from_url(
                    self.settings.redis_url,
                    decode_responses=True,
                )
                pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
                pubsub.subscribe(self.settings.signal_broadcast_channel)
                while not self._listener_stop.is_set():
                    message = pubsub.get_message(timeout=1.0)
                    if not message or message.get("type") != "message":
                        continue
                    data = message.get("data")
                    if not isinstance(data, str):
                        continue
                    try:
                        payload = json.loads(data)
                    except json.JSONDecodeError:
                        logger.warning(
                            "websocket_signal_decode_failed",
                            extra={
                                "event": "websocket_signal_decode_failed",
                                "context": {
                                    "channel": self.settings.signal_broadcast_channel,
                                },
                            },
                        )
                        continue
                    if self._loop is not None:
                        asyncio.run_coroutine_threadsafe(
                            self.broadcast(payload),
                            self._loop,
                        )
            except Exception as exc:  # pragma: no cover
                logger.warning(
                    "websocket_signal_listener_failed",
                    extra={
                        "event": "websocket_signal_listener_failed",
                        "context": {"error": str(exc)[:200]},
                    },
                )
                if not self._listener_stop.wait(reconnect_delay):
                    continue
            finally:
                if pubsub is not None:
                    try:
                        pubsub.close()
                    except Exception:
                        pass
                if redis_client is not None:
                    try:
                        redis_client.close()
                    except Exception:
                        pass


@lru_cache
def get_signal_websocket_manager() -> SignalWebSocketManager:
    return SignalWebSocketManager(get_settings())
