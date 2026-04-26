import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.append(str(Path(__file__).resolve().parents[1]))

try:
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ModuleNotFoundError:
    FASTAPI_AVAILABLE = False

from app.core.config import get_settings
from app.services.api_key_auth import get_api_key_auth_service
from app.services.container import get_container


class StubSignalWebSocketManager:
    def __init__(self):
        self.start_calls = 0
        self.stop_calls = 0

    async def start(self) -> None:
        self.start_calls += 1

    async def stop(self) -> None:
        self.stop_calls += 1


class StubCacheClient:
    def ping(self) -> bool:
        return True


class StubCache:
    def __init__(self):
        self.client = StubCacheClient()


class StubFirestore:
    client = None


class StubMarketData:
    latest_stream_price = {}

    async def fetch_latest_price(self, symbol: str) -> float:
        return 0.0


class StubContainer:
    def __init__(self):
        self.cache = StubCache()
        self.firestore = StubFirestore()
        self.market_data = StubMarketData()


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi is not installed")
class AppBootTest(unittest.TestCase):
    def setUp(self):
        get_settings.cache_clear()
        get_api_key_auth_service.cache_clear()
        settings = get_settings()
        settings.auth_api_keys_json = json.dumps(
            [{"api_key": "boot-token", "user_id": "alice", "key_id": "boot-key"}]
        )
        settings.firestore_project_id = ""
        settings.auth_cache_ttl_seconds = 60

        self.ws_manager = StubSignalWebSocketManager()
        self.ws_patch = patch("app.main.get_signal_websocket_manager", return_value=self.ws_manager)
        self.ws_patch.start()

        from app.main import app

        self.app = app
        self.app.dependency_overrides[get_container] = lambda: StubContainer()

    def tearDown(self):
        self.app.dependency_overrides.clear()
        self.ws_patch.stop()
        get_api_key_auth_service.cache_clear()
        get_settings.cache_clear()

    def test_app_boot_lifecycle_and_core_routes(self):
        with patch("app.main.logger.info") as main_info_log, patch(
            "app.middleware.request_context.logger.info"
        ) as request_info_log:
            with TestClient(self.app) as client:
                root_response = client.get("/", headers={"X-API-Key": "boot-token"})
                self.assertEqual(root_response.status_code, 200)
                self.assertEqual(root_response.json()["status"], "running")

                live_response = client.get("/health/live")
                self.assertEqual(live_response.status_code, 200)
                self.assertEqual(live_response.json()["status"], "alive")

                ready_response = client.get("/health/ready")
                self.assertEqual(ready_response.status_code, 200)
                self.assertEqual(ready_response.json()["status"], "ready")
                self.assertTrue(ready_response.json()["all_ready"])

        self.assertEqual(self.ws_manager.start_calls, 1)
        self.assertEqual(self.ws_manager.stop_calls, 1)
        self.assertEqual(main_info_log.call_count, 3)
        self.assertEqual(main_info_log.call_args_list[0].args[0], "Trading system startup - all services initialized")
        self.assertEqual(main_info_log.call_args_list[1].args[0], "Trading system shutdown - cleaning up resources...")
        self.assertEqual(main_info_log.call_args_list[2].args[0], "Shutdown complete")
        request_info_log.assert_called_once()
        self.assertEqual(request_info_log.call_args.args[0], "request_completed")
        self.assertEqual(request_info_log.call_args.kwargs["extra"]["context"]["path"], "/")
        self.assertEqual(request_info_log.call_args.kwargs["extra"]["context"]["user_id"], "alice")


if __name__ == "__main__":
    unittest.main()
