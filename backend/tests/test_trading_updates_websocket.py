import asyncio
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api.routes import realtime
from app.core.config import get_settings
from app.services.api_key_auth import get_api_key_auth_service
from app.services.websocket_manager import TradingUpdateWebSocketManager, get_trading_update_websocket_manager


class TradingUpdatesWebSocketTest(unittest.TestCase):
    def setUp(self):
        get_settings.cache_clear()
        get_api_key_auth_service.cache_clear()
        get_trading_update_websocket_manager.cache_clear()
        settings = get_settings()
        settings.auth_api_keys_json = json.dumps(
            [
                {"api_key": "ws-token", "user_id": "alice", "key_id": "alice-ws"},
                {"api_key": "other-token", "user_id": "bob", "key_id": "bob-ws"},
            ]
        )
        settings.firestore_project_id = ""
        settings.auth_cache_ttl_seconds = 60
        self.manager = TradingUpdateWebSocketManager()
        self.manager_patch = patch(
            "app.api.routes.realtime.get_trading_update_websocket_manager",
            return_value=self.manager,
        )
        self.manager_patch.start()

        app = FastAPI()
        app.include_router(realtime.router)
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.manager_patch.stop()
        get_api_key_auth_service.cache_clear()
        get_settings.cache_clear()
        get_trading_update_websocket_manager.cache_clear()

    def test_rejects_invalid_query_token(self):
        with self.assertRaises(WebSocketDisconnect) as ctx:
            with self.client.websocket_connect("/api/v1/ws/trading-updates?token=invalid"):
                pass

        self.assertEqual(ctx.exception.code, 1008)

    def test_accepts_query_token_and_ping(self):
        with self.client.websocket_connect("/api/v1/ws/trading-updates?token=ws-token") as websocket:
            websocket.send_text("ping")
            received = websocket.receive_json()

        self.assertEqual(received["event"], "pong")

    def test_broadcasts_chart_order_action_to_matching_user(self):
        with self.client.websocket_connect("/api/v1/ws/trading-updates?token=ws-token") as websocket:
            delivered = asyncio.run(
                self.manager.broadcast_chart_order_action(
                    user_id="alice",
                    action={
                        "action_id": "action-1",
                        "symbol": "BTCUSDT",
                        "chart_order_id": "chart-1",
                        "side": "BUY",
                        "action_type": "SYNC_MOCK_TESTNET_ORDER",
                        "price": 68500.0,
                        "quantity": 0.1,
                        "is_ai_trailing": False,
                        "mode": "mock",
                        "action_payload": {
                            "accepted": True,
                            "live_broker_submission": False,
                            "reason": "chart line mapped",
                        },
                    },
                )
            )
            received = websocket.receive_json()

        self.assertEqual(delivered, 1)
        self.assertEqual(received["event"], "chart_order_action")
        self.assertEqual(received["data"]["symbol"], "BTCUSDT")
        self.assertEqual(received["data"]["action_id"], "action-1")
        self.assertEqual(received["data"]["chart_order_id"], "chart-1")
        self.assertEqual(received["data"]["type"], "LIMIT_BUY")
        self.assertEqual(received["data"]["status"], "MOCK_FILLED")
        self.assertEqual(received["data"]["price"], 68500.0)
        self.assertEqual(received["data"]["quantity"], 0.1)
        self.assertFalse(received["data"]["live_broker_submission"])

    def test_does_not_broadcast_to_other_users(self):
        with self.client.websocket_connect("/api/v1/ws/trading-updates?token=other-token"):
            delivered = asyncio.run(
                self.manager.broadcast_chart_order_action(
                    user_id="alice",
                    action={
                        "action_id": "action-2",
                        "symbol": "ETHUSDT",
                        "side": "SELL",
                        "action_type": "SYNC_MOCK_TESTNET_ORDER",
                        "is_ai_trailing": True,
                        "mode": "mock",
                        "action_payload": {"accepted": True, "live_broker_submission": False},
                    },
                )
            )

        self.assertEqual(delivered, 0)

    def test_broadcasts_strategy_performance_update(self):
        with self.client.websocket_connect("/api/v1/ws/trading-updates?token=ws-token") as websocket:
            delivered = asyncio.run(
                self.manager.broadcast_strategy_performance_update(
                    user_id="alice",
                    snapshot={
                        "timestamp": "2026-05-30T17:24:00Z",
                        "user_id": "alice",
                        "advisory_only": True,
                        "simulation_only": True,
                        "live_broker_submission": False,
                        "action_count": 3,
                        "sharpe_estimate": 1.2,
                        "stress_simulation": {
                            "advisory_only": True,
                            "simulation_only": True,
                            "worst_case_drawdown": 42.0,
                        },
                    },
                )
            )
            received = websocket.receive_json()

        self.assertEqual(delivered, 1)
        self.assertEqual(received["event"], "strategy_performance_update")
        self.assertEqual(received["data"]["user_id"], "alice")
        self.assertTrue(received["data"]["advisory_only"])
        self.assertTrue(received["data"]["simulation_only"])
        self.assertFalse(received["data"]["live_broker_submission"])
        self.assertEqual(received["data"]["stress_simulation"]["worst_case_drawdown"], 42.0)


if __name__ == "__main__":
    unittest.main()
