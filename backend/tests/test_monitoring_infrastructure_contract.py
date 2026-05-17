import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.append(str(Path(__file__).resolve().parents[1]))

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    FASTAPI_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - lightweight dependency guard
    FASTAPI_AVAILABLE = False

from app.api.routes import monitoring
from app.core.config import get_settings
from app.middleware.auth import AuthMiddleware
from app.services.api_key_auth import get_api_key_auth_service
from app.services.container import get_container
from app.services.redis_cache import RedisCache


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi is not installed")
class MonitoringInfrastructureContractTest(unittest.TestCase):
    def setUp(self) -> None:
        get_settings.cache_clear()
        get_api_key_auth_service.cache_clear()
        settings = get_settings()
        settings.firestore_project_id = ""
        settings.auth_cache_ttl_seconds = 30
        settings.auth_api_keys_json = json.dumps(
            [{"api_key": "ops-test-key", "user_id": "ops-user", "key_id": "ops-key"}]
        )

        self.cache = RedisCache("")
        self.cache.set("monitor:websocket_sequence_gaps", "2")
        self.cache.set("monitor:websocket_replay_frequency", "3")
        self.cache.set("monitor:websocket_stale_feed_count", "1")
        self.cache.set("monitor:websocket_latency_ms", "42.5")
        self.cache.set("monitor:chart_fps", "58.0")
        self.cache.set("monitor:overlay_pressure", "0.37")
        self.cache.set("monitor:event_bus_market_throughput", "120")
        self.cache.set("monitor:event_bus_ai_throughput", "35")
        self.cache.set("monitor:event_bus_analytics_throughput", "15")
        self.cache.set("monitor:ai_worker_latency_ms", "88.0")
        self.cache.set("monitor:gpu_inference_latency_ms", "61.0")
        self.cache.set_json(
            "realtime:last:chart_snapshot",
            {"type": "chart_snapshot", "symbol": "BTCUSDT", "sequence": 1005},
            ttl=60,
        )

        app = FastAPI()
        app.add_middleware(AuthMiddleware)
        app.include_router(monitoring.router, prefix="/v1")
        app.dependency_overrides[get_container] = lambda: SimpleNamespace(cache=self.cache)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        get_api_key_auth_service.cache_clear()
        get_settings.cache_clear()

    def test_realtime_infrastructure_contract_includes_operational_sections(self) -> None:
        response = self.client.get(
            "/v1/monitoring/infrastructure/realtime",
            headers={"X-API-Key": "ops-test-key"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        for key in [
            "timestamp",
            "redis",
            "websocket",
            "ai_workers",
            "rendering",
            "event_bus",
            "gpu_inference",
            "high_availability",
            "slo",
            "replay_checkpoint",
            "incident",
            "retention",
            "capacity",
            "runbook",
            "release",
            "canary",
            "rollback",
            "backup",
            "audit_export",
            "config_drift",
            "synthetic_probes",
            "disaster_recovery",
            "data_lineage",
            "compliance",
            "readiness",
            "brokers",
            "execution_latency_ms",
        ]:
            self.assertIn(key, payload)

        self.assertEqual(payload["websocket"]["sequence_gaps"], 2)
        self.assertEqual(payload["websocket"]["last_chart_snapshot"]["sequence"], 1005)
        self.assertEqual(payload["event_bus"]["market_throughput"], 120)
        self.assertIn("mode", payload["slo"])
        self.assertIn("status", payload["release"])
        self.assertIn("state", payload["compliance"])
        self.assertIn("status", payload["readiness"])
        self.assertIn("manifest_version", payload["data_lineage"])
        self.assertIsInstance(payload["brokers"], list)


if __name__ == "__main__":
    unittest.main()
