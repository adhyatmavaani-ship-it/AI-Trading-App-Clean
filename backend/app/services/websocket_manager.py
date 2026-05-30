from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
from functools import lru_cache
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from app.core.config import get_settings
from app.core import metrics


logger = logging.getLogger(__name__)


class TradingUpdateWebSocketManager:
    """User-scoped websocket manager for chart/testnet action updates."""

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}
        self._reverse_index: dict[WebSocket, str] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, *, user_id: str) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.setdefault(user_id, set()).add(websocket)
            self._reverse_index[websocket] = user_id
            connection_count = sum(len(items) for items in self._connections.values())
        logger.info(
            "trading_updates_websocket_connected",
            extra={
                "event": "trading_updates_websocket_connected",
                "context": {"user_id": user_id, "connection_count": connection_count},
            },
        )

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            user_id = self._reverse_index.pop(websocket, None)
            if user_id:
                sockets = self._connections.get(user_id)
                if sockets is not None:
                    sockets.discard(websocket)
                    if not sockets:
                        self._connections.pop(user_id, None)
            connection_count = sum(len(items) for items in self._connections.values())
        logger.info(
            "trading_updates_websocket_disconnected",
            extra={
                "event": "trading_updates_websocket_disconnected",
                "context": {"user_id": user_id or "unknown", "connection_count": connection_count},
            },
        )

    async def broadcast_to_user(self, user_id: str, payload: dict[str, Any]) -> int:
        message = json.dumps(payload, default=str)
        async with self._lock:
            recipients = list(self._connections.get(user_id, set()))
        if not recipients:
            return 0

        settings = get_settings()
        send_timeout_seconds = max(float(settings.websocket_send_timeout_seconds), 0.1)
        stale: list[WebSocket] = []
        delivered = 0
        for websocket in recipients:
            try:
                await asyncio.wait_for(websocket.send_text(message), timeout=send_timeout_seconds)
                delivered += 1
            except TimeoutError:
                stale.append(websocket)
            except (RuntimeError, WebSocketDisconnect):
                stale.append(websocket)
            except Exception as exc:  # pragma: no cover
                stale.append(websocket)
                logger.warning(
                    "trading_updates_websocket_send_failed",
                    extra={
                        "event": "trading_updates_websocket_send_failed",
                        "context": {"user_id": user_id, "error": str(exc)[:200]},
                    },
                )

        for websocket in stale:
            await self.disconnect(websocket)

        if delivered:
            metrics.websocket_events_sent.labels(event_type=str(payload.get("event", "trading_update"))).inc(delivered)
        if stale:
            metrics.websocket_events_dropped.labels(reason="trading_update_stale_connection").inc(len(stale))
        return delivered

    async def broadcast_chart_order_action(self, *, user_id: str, action: dict[str, Any]) -> int:
        action_payload = dict(action.get("action_payload") or {})
        payload = {
            "event": "chart_order_action",
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "data": {
                "symbol": action.get("symbol"),
                "action_id": action.get("action_id"),
                "chart_order_id": action.get("chart_order_id"),
                "type": self._action_type(action),
                "status": self._action_status(action_payload),
                "price": action.get("price"),
                "quantity": action.get("quantity"),
                "is_ai_trailing": bool(action.get("is_ai_trailing")),
                "mode": action.get("mode"),
                "live_broker_submission": bool(action_payload.get("live_broker_submission", False)),
                "reason": action_payload.get("reason"),
            },
        }
        return await self.broadcast_to_user(user_id, payload)

    async def broadcast_strategy_performance_update(self, *, user_id: str, snapshot: dict[str, Any]) -> int:
        payload = {
            "event": "strategy_performance_update",
            "timestamp": snapshot.get("timestamp") or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "data": {
                key: value
                for key, value in snapshot.items()
                if key not in {"event", "timestamp"}
            },
        }
        payload["data"]["advisory_only"] = True
        payload["data"]["simulation_only"] = True
        payload["data"]["live_broker_submission"] = False
        return await self.broadcast_to_user(user_id, payload)

    async def heartbeat(self, websocket: WebSocket, *, interval_seconds: float = 30.0) -> None:
        interval = max(float(interval_seconds), 5.0)
        while True:
            await asyncio.sleep(interval)
            await websocket.send_text(
                json.dumps(
                    {
                        "event": "heartbeat",
                        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    }
                )
            )

    @staticmethod
    def _action_type(action: dict[str, Any]) -> str:
        side = str(action.get("side") or "").upper()
        raw_type = str(action.get("action_type") or "SYNC_ORDER").upper()
        if side in {"BUY", "SELL"} and "SYNC" in raw_type:
            return f"LIMIT_{side}"
        return raw_type

    @staticmethod
    def _action_status(action_payload: dict[str, Any]) -> str:
        if action_payload.get("live_broker_submission") is True:
            return "UNSAFE_LIVE_SUBMISSION_BLOCKED"
        if action_payload.get("accepted") is False:
            return "MOCK_REJECTED"
        return "MOCK_FILLED"


@lru_cache
def get_trading_update_websocket_manager() -> TradingUpdateWebSocketManager:
    return TradingUpdateWebSocketManager()
