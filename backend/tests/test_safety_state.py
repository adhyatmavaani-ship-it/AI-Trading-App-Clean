from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings  # noqa: E402
from app.services.redis_cache import RedisCache  # noqa: E402
from app.services.safety_state import SafetyStateService  # noqa: E402
from db.database import SQLiteTradeDatabase  # noqa: E402


class SafetyStateServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cache = RedisCache("")
        self.settings = Settings(redis_url="", state_heartbeat_max_age_ms=1_000.0)
        self.service = SafetyStateService(settings=self.settings, cache=self.cache)

    def _healthy_state(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.cache.set("monitor:websocket_connected", "1", ttl=60)
        self.cache.set("monitor:websocket_connected:last_seen_ts", now, ttl=60)
        self.cache.set_json("market:feed:health", {"healthy": True, "producer_last_seen_ts": now}, ttl=60)
        self.cache.set_json(
            "broker:reconciliation:last",
            {"mismatch_count": 0, "duplicate_ack_count": 0, "producer_last_seen_ts": now},
            ttl=60,
        )
        self.cache.set_json("ai:latency", {"latency_ms": 10.0, "producer_last_seen_ts": now}, ttl=60)
        self.cache.set_json("exchange:latency", {"latency_ms": 10.0, "producer_last_seen_ts": now}, ttl=60)

    def test_live_execution_fails_closed_when_keys_are_missing(self):
        payload = self.service.snapshot(trading_mode="live")

        self.assertFalse(payload["execution_available"])
        self.assertFalse(payload["components"]["websocket"]["healthy"])
        self.assertFalse(payload["components"]["feed"]["healthy"])

    def test_stale_producer_is_unhealthy(self):
        self._healthy_state()
        stale = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
        self.cache.set("monitor:websocket_connected:last_seen_ts", stale, ttl=60)

        payload = self.service.snapshot(trading_mode="live")

        self.assertFalse(payload["execution_available"])
        self.assertEqual(payload["components"]["websocket"]["reason"], "websocket producer stale")
        self.assertGreater(payload["components"]["websocket"]["producer_age_ms"], 1000.0)

    def test_paper_execution_remains_available_during_degraded_state(self):
        payload = self.service.snapshot(trading_mode="paper")

        self.assertTrue(payload["execution_available"])
        self.assertFalse(payload["components"]["websocket"]["healthy"])

    def test_operational_snapshot_includes_db_pressure_and_worker_heartbeats(self):
        self._healthy_state()
        now = datetime.now(timezone.utc).isoformat()
        self.cache.set("worker:broker_reconciliation:heartbeat", now, ttl=60)
        self.cache.set("monitor:execution_circuit_breaker_open_total", "2", ttl=60)
        with tempfile.TemporaryDirectory() as temp_dir:
            store = SQLiteTradeDatabase(Path(temp_dir) / "ops.sqlite3")
            store.append_execution_audit_event("exec_ops", "execution_requested", {})
            service = SafetyStateService(settings=self.settings, cache=self.cache, store=store)

            payload = service.snapshot(trading_mode="live")

        self.assertTrue(payload["execution_available"])
        self.assertTrue(payload["db_write_pressure"]["available"])
        self.assertGreaterEqual(payload["db_write_pressure"]["transactions"], 1)
        self.assertEqual(payload["operational_metrics"]["execution_circuit_breaker_open_total"], 2)
        self.assertTrue(payload["worker_heartbeats"]["worker:broker_reconciliation:heartbeat"]["healthy"])


if __name__ == "__main__":
    unittest.main()
