import sys
import unittest
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


class RolloutManagerInstitutionalTest(unittest.TestCase):
    def test_rollout_downgrades_on_drawdown(self):
        cache = InMemoryCache()
        settings = Settings(trading_mode="live", rollout_stages=[0.0, 0.01, 0.1, 0.25])
        manager = RolloutManager(settings, cache)
        cache.set_json(
            "rollout:status",
            {
                "stage_index": 3,
                "stage_name": "EXPANDED",
                "capital_fraction": 0.25,
                "mode": "live",
                "eligible_for_upgrade": True,
                "downgrade_flag": False,
            },
            ttl=3600,
        )

        updated = manager.record_performance(win_rate=0.40, profit_factor=0.8, trades=100, drawdown=0.12)

        self.assertEqual(updated.stage_name, "LIMITED")
        self.assertTrue(updated.downgrade_flag)


if __name__ == "__main__":
    unittest.main()
