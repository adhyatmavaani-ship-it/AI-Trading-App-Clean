import asyncio
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.append(str(Path(__file__).resolve().parents[1]))

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect
    FASTAPI_AVAILABLE = True
except ModuleNotFoundError:
    FASTAPI_AVAILABLE = False

from app.core.config import get_settings
from app.services.api_key_auth import get_api_key_auth_service

if FASTAPI_AVAILABLE:
    from app.api.routes import realtime
    from app.services.signal_websocket_manager import SignalWebSocketManager


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi is not installed")
class RealtimeWebSocketTest(unittest.TestCase):
    def setUp(self):
        get_settings.cache_clear()
        get_api_key_auth_service.cache_clear()
        settings = get_settings()
        settings.auth_api_keys_json = json.dumps(
            [
                {"api_key": "ws-token", "user_id": "alice", "key_id": "alice-ws"},
                {"api_key": "bearer-token", "user_id": "bob", "key_id": "bob-ws"},
            ]
        )
        settings.firestore_project_id = ""
        settings.auth_cache_ttl_seconds = 60
        self.manager = SignalWebSocketManager(settings)
        self.manager_patch = patch(
            "app.api.routes.realtime.get_signal_websocket_manager",
            return_value=self.manager,
        )
        self.manager_patch.start()

        app = FastAPI()
        app.include_router(realtime.router)
        app.include_router(realtime.router, prefix="/v1")
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.manager_patch.stop()
        asyncio.run(self.manager.stop())
        get_api_key_auth_service.cache_clear()
        get_settings.cache_clear()

    def test_rejects_invalid_websocket_api_key(self):
        with self.assertRaises(WebSocketDisconnect) as ctx:
            with self.client.websocket_connect("/ws/signals?api_key=invalid-token"):
                pass

        self.assertEqual(ctx.exception.code, 1008)

    def test_accepts_ping_and_broadcasts_signal_for_x_api_key(self):
        with self.client.websocket_connect(
            "/ws/signals",
            headers={"X-API-Key": "ws-token"},
        ) as websocket:
            websocket.send_text("ping")
            self.assertEqual(websocket.receive_json(), {"type": "pong"})

            asyncio.run(
                self.manager.broadcast(
                    {"type": "signal", "symbol": "BTCUSDT", "signal_version": 7}
                )
            )

            self.assertEqual(
                websocket.receive_json(),
                {"type": "signal", "symbol": "BTCUSDT", "signal_version": 7},
            )

    def test_accepts_bearer_token_on_versioned_websocket_route(self):
        with self.client.websocket_connect(
            "/v1/ws/signals",
            headers={"Authorization": "Bearer bearer-token"},
        ) as websocket:
            websocket.send_text("ping")
            self.assertEqual(websocket.receive_json(), {"type": "pong"})

            asyncio.run(
                self.manager.broadcast(
                    {"type": "signal", "symbol": "ETHUSDT", "signal_version": 8}
                )
            )

            self.assertEqual(
                websocket.receive_json(),
                {"type": "signal", "symbol": "ETHUSDT", "signal_version": 8},
            )


if __name__ == "__main__":
    unittest.main()
