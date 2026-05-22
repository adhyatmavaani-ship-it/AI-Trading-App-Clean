from __future__ import annotations

import sys
import unittest
from pathlib import Path
from datetime import datetime, timezone

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings  # noqa: E402
from app.services.execution_circuit_breaker import ExecutionCircuitBreaker  # noqa: E402
from app.services.redis_cache import RedisCache  # noqa: E402


class ExecutionCircuitBreakerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cache = RedisCache("")
        self.settings = Settings(
            redis_url="",
            trading_mode="live",
            execution_ai_timeout_threshold_ms=500.0,
            execution_exchange_latency_threshold_ms=300.0,
        )
        self.breaker = ExecutionCircuitBreaker(settings=self.settings, cache=self.cache)

    def _healthy_state(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.cache.set("monitor:websocket_connected", "1", ttl=60)
        self.cache.set("monitor:websocket_connected:last_seen_ts", now, ttl=60)
        self.cache.set_json(
            "market:feed:health",
            {"healthy": True, "producer_last_seen_ts": now, "health_reason": "healthy"},
            ttl=60,
        )
        self.cache.set_json(
            "broker:reconciliation:last",
            {"mismatch_count": 0, "duplicate_ack_count": 0, "producer_last_seen_ts": now},
            ttl=60,
        )
        self.cache.set_json("ai:latency", {"latency_ms": 100.0, "producer_last_seen_ts": now}, ttl=60)
        self.cache.set_json("exchange:latency", {"latency_ms": 100.0, "producer_last_seen_ts": now}, ttl=60)

    def test_allows_paper_mode_by_default(self):
        self.cache.set_json("market:feed:health", {"healthy": False}, ttl=60)

        decision = self.breaker.evaluate(trading_mode="paper", symbol="BTCUSDT")

        self.assertTrue(decision.allowed)

    def test_missing_live_state_fails_closed(self):
        decision = self.breaker.evaluate(trading_mode="live", symbol="BTCUSDT")

        self.assertFalse(decision.allowed)
        self.assertIn("websocket state missing", decision.reasons)
        self.assertIn("market feed health missing", decision.reasons)
        self.assertIn("broker reconciliation missing", decision.reasons)
        self.assertIn("ai_latency missing", decision.reasons)
        self.assertIn("exchange_latency missing", decision.reasons)

    def test_blocks_live_when_market_feed_is_unhealthy(self):
        self._healthy_state()
        self.cache.set_json(
            "market:feed:health",
            {
                "healthy": False,
                "reasons": ["market feed stale"],
                "producer_last_seen_ts": datetime.now(timezone.utc).isoformat(),
            },
            ttl=60,
        )

        decision = self.breaker.evaluate(trading_mode="live", symbol="BTCUSDT")

        self.assertFalse(decision.allowed)
        self.assertIn("market feed stale", decision.reasons)
        self.assertIsNotNone(self.cache.get_json("execution:circuit:last_block"))
        self.assertEqual(int(self.cache.get("monitor:execution_circuit_breaker_open_total") or 0), 1)

    def test_blocks_live_on_reconciliation_mismatch_and_latency(self):
        self._healthy_state()
        now = datetime.now(timezone.utc).isoformat()
        self.cache.set_json("broker:reconciliation:last", {"mismatch_count": 2, "producer_last_seen_ts": now}, ttl=60)
        self.cache.set_json("ai:latency", {"latency_ms": 900, "producer_last_seen_ts": now}, ttl=60)
        self.cache.set_json("exchange:latency", {"latency_ms": 450, "producer_last_seen_ts": now}, ttl=60)

        decision = self.breaker.evaluate(trading_mode="live", symbol="ETHUSDT")

        self.assertFalse(decision.allowed)
        self.assertIn("broker reconciliation mismatch", decision.reasons)
        self.assertIn("ai_latency too high", decision.reasons)
        self.assertIn("exchange_latency too high", decision.reasons)

    def test_blocks_live_when_websocket_is_disconnected(self):
        self._healthy_state()
        self.cache.set("monitor:websocket_connected", "0", ttl=60)

        decision = self.breaker.evaluate(trading_mode="live", symbol="SOLUSDT")

        self.assertFalse(decision.allowed)
        self.assertIn("websocket disconnected", decision.reasons)


if __name__ == "__main__":
    unittest.main()
