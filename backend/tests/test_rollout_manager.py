import unittest
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.rollout_manager import RolloutManager


class InMemoryCache:
    def __init__(self):
        self.store = {}

    def get_json(self, key):
        return self.store.get(key)

    def set_json(self, key, value, ttl):
        self.store[key] = value

    def publish(self, channel, message):
        self.store[f"pub:{channel}"] = message
        return 1


class RolloutManagerTest(unittest.TestCase):
    def test_rollout_manager_scales_after_good_performance(self):
        cache = InMemoryCache()
        settings = Settings(trading_mode="paper", rollout_stages=[0.01, 0.05, 0.10], rollout_min_trades=20)
        manager = RolloutManager(settings, cache)

        updated = manager.record_performance(win_rate=0.60, profit_factor=1.4, trades=25)

        self.assertEqual(updated.stage_index, 1)
        self.assertEqual(updated.capital_fraction, 0.05)


if __name__ == "__main__":
    unittest.main()
