from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from functools import lru_cache

from fastapi import WebSocket
from redis import Redis
from starlette.websockets import WebSocketDisconnect

from app.core.config import Settings, get_settings
from app.core import metrics
from app.services.realtime_integrity import RealtimeIntegritySequencer, RealtimeReplayBuffer


logger = logging.getLogger(__name__)


class SignalWebSocketManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._connections: dict[WebSocket, str] = {}
        self._stream_filters: dict[WebSocket, set[str]] = {}
        self._lock = asyncio.Lock()
        self._listener_thread: threading.Thread | None = None
        self._listener_stop = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._sequencer = RealtimeIntegritySequencer()
        self._replay_buffer = RealtimeReplayBuffer()

    async def connect(self, websocket: WebSocket, user_id: str, stream_filters: set[str] | None = None) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[websocket] = user_id
            if stream_filters:
                self._stream_filters[websocket] = set(stream_filters)
            connection_count = len(self._connections)
        logger.info(
            "websocket_client_connected",
            extra={
                "event": "websocket_client_connected",
                "context": {
                    "user_id": user_id,
                    "connection_count": connection_count,
                },
            },
        )

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            user_id = self._connections.pop(websocket, None)
            self._stream_filters.pop(websocket, None)
            connection_count = len(self._connections)
        logger.info(
            "websocket_client_disconnected",
            extra={
                "event": "websocket_client_disconnected",
                "context": {
                    "user_id": user_id or "unknown",
                    "connection_count": connection_count,
                },
            },
        )

    async def broadcast(self, payload: dict) -> None:
        started = time.perf_counter()
        envelope = self._sequencer.envelope(payload)
        if envelope is None:
            metrics.websocket_events_dropped.labels(reason="duplicate").inc()
            return
        self._replay_buffer.append(envelope)
        message = json.dumps(envelope, default=str)
        async with self._lock:
            recipients = list(self._connections.items())

        stale_connections: list[WebSocket] = []
        delivered_count = 0
        send_timeout_seconds = max(float(self.settings.websocket_send_timeout_seconds), 0.1)
        for websocket, user_id in recipients:
            filters = self._stream_filters.get(websocket)
            if filters and str(envelope.get("stream_group") or envelope.get("type") or "") not in filters:
                continue
            try:
                await asyncio.wait_for(websocket.send_text(message), timeout=send_timeout_seconds)
                delivered_count += 1
            except TimeoutError:
                logger.warning(
                    "websocket_broadcast_timed_out",
                    extra={
                        "event": "websocket_broadcast_timed_out",
                        "context": {
                            "user_id": user_id,
                            "timeout_seconds": send_timeout_seconds,
                            "payload_type": envelope.get("type", "unknown"),
                        },
                    },
                )
                stale_connections.append(websocket)
            except (WebSocketDisconnect, RuntimeError):
                stale_connections.append(websocket)
            except Exception as exc:  # pragma: no cover
                logger.warning(
                    "websocket_broadcast_failed",
                    extra={
                        "event": "websocket_broadcast_failed",
                        "context": {
                            "user_id": user_id,
                            "error": str(exc)[:200],
                            "payload_type": envelope.get("type", "unknown"),
                        },
                    },
                )
                stale_connections.append(websocket)

        for websocket in stale_connections:
            await self.disconnect(websocket)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        metrics.websocket_broadcast_latency.observe(duration_ms / 1000)
        metrics.websocket_events_sent.labels(
            event_type=str(envelope.get("type", "unknown"))
        ).inc(delivered_count)
        if stale_connections:
            metrics.websocket_events_dropped.labels(reason="stale_connection").inc(len(stale_connections))
        if duration_ms >= self.settings.slow_operation_threshold_seconds * 1000:
            logger.warning(
                "websocket_broadcast_slow",
                extra={
                    "event": "websocket_broadcast_slow",
                    "context": {
                        "duration_ms": duration_ms,
                        "recipient_count": len(recipients),
                        "stale_connection_count": len(stale_connections),
                        "payload_type": envelope.get("type", "unknown"),
                    },
                },
            )

    async def replay(self, websocket: WebSocket, payload: dict) -> dict:
        stream = str(payload.get("stream") or payload.get("type") or "event")
        from_sequence = int(payload.get("from_sequence") or 0)
        to_sequence = int(payload.get("to_sequence") or from_sequence)
        events = self._replay_buffer.replay(
            stream=stream,
            from_sequence=from_sequence,
            to_sequence=to_sequence,
        )
        for event in events:
            await websocket.send_text(json.dumps(event, default=str))
        metrics.websocket_replay_requests.labels(
            stream=stream,
            status="hit" if events else "miss",
        ).inc()
        return {
            "type": "replay_response",
            "stream": stream,
            "from_sequence": from_sequence,
            "to_sequence": to_sequence,
            "event_count": len(events),
            "recovery": "replay" if events else "snapshot_required",
        }

    async def start(self) -> None:
        if not self.settings.websocket_listener_enabled:
            return
        if not (self.settings.redis_url or "").strip():
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
        redis_url = (self.settings.redis_url or "").strip()
        if not redis_url:
            return
        reconnect_delay = max(float(self.settings.websocket_redis_reconnect_seconds), 0.1)
        while not self._listener_stop.is_set():
            redis_client: Redis | None = None
            pubsub = None
            try:
                logger.info(
                    "websocket_signal_listener_connecting",
                    extra={
                        "event": "websocket_signal_listener_connecting",
                        "context": {"reconnect_delay_seconds": reconnect_delay},
                    },
                )
                redis_client = Redis.from_url(
                    redis_url,
                    decode_responses=True,
                )
                pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
                for channel in (
                    self.settings.signal_broadcast_channel,
                    self.settings.live_activity_channel,
                ):
                    pubsub.subscribe(channel)
                logger.info(
                    "websocket_signal_listener_connected",
                    extra={
                        "event": "websocket_signal_listener_connected",
                        "context": {
                            "channels": [
                                self.settings.signal_broadcast_channel,
                                self.settings.live_activity_channel,
                            ],
                        },
                    },
                )
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
                                    "channels": [self.settings.signal_broadcast_channel, self.settings.live_activity_channel],
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
                        "context": {
                            "error": str(exc)[:200],
                            "reconnect_delay_seconds": reconnect_delay,
                        },
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
