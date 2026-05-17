import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.chart_intelligence import build_chart_intelligence  # noqa: E402
from app.services.infrastructure_slo import InfrastructureSLOEngine  # noqa: E402
from app.services.orderbook_delta_validator import OrderbookDeltaValidator  # noqa: E402
from app.services.redis_cache import RedisCache  # noqa: E402
from app.services.render_profile_engine import RenderProfileEngine  # noqa: E402
from app.services.replay_checkpoint_store import ReplayCheckpointStore  # noqa: E402


class Phase6OperationalGuardrailsTest(unittest.TestCase):
    def _frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "open_time": 1714212000000 + index * 60000,
                    "close_time": 1714212060000 + index * 60000,
                    "open": 100 + index * 0.12,
                    "high": 100.4 + index * 0.16,
                    "low": 99.7 + index * 0.10,
                    "close": 100.2 + index * 0.14,
                    "volume": 1000 + index * 40,
                }
                for index in range(40)
            ]
        )

    def test_slo_engine_escalates_incident_mode(self):
        status = InfrastructureSLOEngine().evaluate(
            websocket_latency_ms=900,
            sequence_gaps=4,
            stale_feeds=2,
            ai_queue_depth=600,
            gpu_queue_depth=300,
            render_fps=35,
            redis_fallback=True,
        ).as_dict()

        self.assertEqual(status["mode"], "INCIDENT")
        self.assertTrue(status["breaches"])
        self.assertIn("force snapshot resume and pause stale chart rendering", status["actions"])

    def test_render_profile_switches_to_low_power(self):
        profile = RenderProfileEngine().profile(
            overlay_count=80,
            heatmap_zones=10,
            dom_levels=40,
            fps=38,
        )

        self.assertEqual(profile["mode"], "LOW_POWER")
        self.assertEqual(profile["target_fps"], 30)
        self.assertLessEqual(profile["max_dom_levels"], 8)

    def test_replay_checkpoint_validates_state_hash(self):
        cache = RedisCache("")
        store = ReplayCheckpointStore(cache)
        checkpoint = store.save(
            stream="chart_snapshot",
            sequence_id=12,
            state={"symbol": "BTCUSDT", "latest_price": 100.0},
        )
        validation = store.validate(stream="chart_snapshot")

        self.assertEqual(checkpoint["sequence_id"], 12)
        self.assertTrue(validation["valid"])

    def test_orderbook_delta_validator_requests_replay_on_gap(self):
        result = OrderbookDeltaValidator().validate(
            current_sequence=10,
            incoming_sequence=13,
            bid_updates=[(100.0, 1.0)],
            ask_updates=[(100.1, 1.0)],
        )

        self.assertFalse(result["valid"])
        self.assertEqual(result["action"], "REQUEST_REPLAY")
        self.assertEqual(result["missing_range"], [11, 12])

    def test_chart_payload_contains_render_profile(self):
        payload = build_chart_intelligence(
            symbol="BTCUSDT",
            interval="5m",
            frame=self._frame(),
        )

        profile = payload["render_hints"]["render_profile"]
        self.assertIn(profile["mode"], {"PRO", "BALANCED", "LOW_POWER"})
        self.assertIn("max_dom_levels", profile)


if __name__ == "__main__":
    unittest.main()
