import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.ai_context_memory import AIContextMemory  # noqa: E402
from app.services.ai_worker_queue import AIWorkerQueue  # noqa: E402
from app.services.distributed_event_bus import DistributedEventBus  # noqa: E402
from app.services.market_regime_engine import MarketRegimeEngine  # noqa: E402
from app.services.redis_cache import RedisCache  # noqa: E402
from app.services.realtime_integrity import RealtimeIntegritySequencer  # noqa: E402
from app.services.time_series_store import TimeSeriesStore  # noqa: E402


class Phase3InfrastructureTest(unittest.TestCase):
    def _frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "open": 100 + index * 0.35,
                    "high": 100.4 + index * 0.40,
                    "low": 99.8 + index * 0.28,
                    "close": 100.2 + index * 0.38,
                    "volume": 1000 + index * 25,
                }
                for index in range(32)
            ]
        )

    def test_realtime_envelope_adds_snapshot_integrity(self):
        envelope = RealtimeIntegritySequencer().envelope(
            {"type": "chart_snapshot", "symbol": "BTCUSDT", "latest_price": 100.0}
        )

        self.assertIsNotNone(envelope)
        self.assertGreater(envelope["snapshot_version"], 0)
        self.assertTrue(envelope["state_hash"])
        self.assertTrue(envelope["integrity_checksum"])
        self.assertEqual(envelope["realtime"]["integrity_checksum"], envelope["integrity_checksum"])

    def test_event_bus_streams_and_replays_events(self):
        cache = RedisCache("")
        bus = DistributedEventBus(cache)

        result = bus.publish(
            channel="signals:test",
            event_type="chart_snapshot",
            payload={"symbol": "BTCUSDT"},
            partition_key="BTCUSDT",
        )
        replayed = bus.replay(event_type="chart_snapshot", partition_key="BTCUSDT")

        self.assertIsNotNone(result.stream_id)
        self.assertEqual(replayed[0]["symbol"], "BTCUSDT")
        self.assertEqual(replayed[0]["event_type"], "chart_snapshot")

    def test_ai_worker_queue_orders_due_jobs(self):
        cache = RedisCache("")
        queue = AIWorkerQueue(cache)

        queue.enqueue(job_type="smc_analysis", symbol="BTCUSDT", payload={"window": 96})
        jobs = queue.dequeue(limit=5)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].job_type, "smc_analysis")
        self.assertEqual(jobs[0].symbol, "BTCUSDT")

    def test_regime_engine_detects_market_state(self):
        regime = MarketRegimeEngine().analyze(self._frame())

        self.assertIn(regime.regime, {"TRENDING", "EXPANSION", "RANGING", "COMPRESSION", "ACCUMULATION", "DISTRIBUTION"})
        self.assertGreaterEqual(regime.confidence, 0.0)
        self.assertIn("risk_multiplier", regime.ai_modifiers)

    def test_ai_context_memory_adjusts_confidence(self):
        cache = RedisCache("")
        memory = AIContextMemory(cache)

        summary = memory.remember(
            symbol="BTCUSDT",
            event_type="failed_breakout",
            payload={"level": 100.0},
        )

        self.assertLess(summary["confidence_adjustment"], 0.0)
        self.assertEqual(memory.load_summary(symbol="BTCUSDT")["recent_event_count"], 1)

    def test_time_series_store_appends_rows(self):
        cache = RedisCache("")
        store = TimeSeriesStore(cache)

        result = store.append(namespace="candles:BTCUSDT:1m", payload={"close": 100.0})
        rows = store.range(namespace="candles:BTCUSDT:1m")

        self.assertIsNotNone(result.stream_id)
        self.assertEqual(rows[0]["close"], 100.0)


if __name__ == "__main__":
    unittest.main()
