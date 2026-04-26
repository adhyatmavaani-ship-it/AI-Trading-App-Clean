import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.generative_simulation_engine import GenerativeSimulationEngine


class InMemoryCache:
    def __init__(self):
        self.store = {}

    def get_json(self, key):
        return self.store.get(key)

    def set_json(self, key, value, ttl=None):
        self.store[key] = value


class StubFirestore:
    def __init__(self):
        self.snapshots = {}

    def save_performance_snapshot(self, user_id, payload):
        self.snapshots[user_id] = payload


class GenerativeSimulationEngineTest(unittest.TestCase):
    def test_generates_probability_heatmap(self):
        engine = GenerativeSimulationEngine(
            settings=Settings(model_dir=str(Path.cwd() / "tmp-gan"), redis_url="redis://unused"),
            cache=InMemoryCache(),
            firestore=StubFirestore(),
        )

        report = engine.dream_market_paths(
            symbol="BTCUSDT",
            base_price=100000.0,
            horizon_minutes=15,
            path_count=2000,
            shock_scenario={"btc_drop_pct": 0.05, "inflation_surprise": 0.02},
        )

        self.assertEqual(report["path_count"], 2000)
        self.assertEqual(len(report["heatmap"]), 4)
        self.assertIn("probability of bounce", report["headline"])


if __name__ == "__main__":
    unittest.main()
