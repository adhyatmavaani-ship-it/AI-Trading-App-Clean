import asyncio
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.analytics_service import AnalyticsService
from app.services.redis_state_manager import RedisStateManager
from app.services.strategy_controller import StrategyController
from app.workers.strategy_optimizer_worker import StrategyOptimizerWorker


class InMemoryCache:
    def __init__(self):
        self.store = {}

    def get_json(self, key):
        return self.store.get(key)

    def set_json(self, key, value, ttl):
        self.store[key] = value

    def delete(self, key):
        self.store.pop(key, None)

    def keys(self, pattern):
        prefix = pattern.replace("*", "")
        return [key for key in self.store if key.startswith(prefix)]


class StrategyControllerTest(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(redis_url="redis://unused")
        self.cache = InMemoryCache()
        self.redis_state_manager = RedisStateManager(self.settings, self.cache)
        self.analytics = AnalyticsService(
            settings=self.settings,
            cache=self.cache,
            redis_state_manager=self.redis_state_manager,
            firestore=None,
        )
        self.controller = StrategyController(
            settings=self.settings,
            analytics=self.analytics,
            cache=self.cache,
        )

    def test_adjust_weights_applies_feedback_and_bounds(self):
        self.cache.set_json(
            "analytics:history:system",
            {
                "trades": [
                    {"status": "CLOSED", "symbol": "BTCUSDT", "regime": "TRENDING", "profit_pct": 1.0, "max_profit": 1.8, "exit_reason": "structure_break", "exit_type": "early_exit", "entry_reason": "structure + momentum", "tags": ["strict_confluence"]},
                    {"status": "CLOSED", "symbol": "BTCUSDT", "regime": "TRENDING", "profit_pct": 1.1, "max_profit": 1.9, "exit_reason": "structure_break", "exit_type": "early_exit", "entry_reason": "structure + momentum", "tags": ["strict_confluence"]},
                    {"status": "CLOSED", "symbol": "BTCUSDT", "regime": "TRENDING", "profit_pct": 0.9, "max_profit": 2.1, "exit_reason": "structure_break", "exit_type": "early_exit", "entry_reason": "structure + momentum", "tags": ["strict_confluence"]},
                    {"status": "CLOSED", "symbol": "ETHUSDT", "regime": "TRENDING", "profit_pct": -0.5, "max_profit": 0.1, "exit_reason": "volume_reversal", "exit_type": "early_exit", "entry_reason": "volume + momentum", "tags": []},
                    {"status": "CLOSED", "symbol": "ETHUSDT", "regime": "TRENDING", "profit_pct": -0.3, "max_profit": 0.1, "exit_reason": "volume_reversal", "exit_type": "early_exit", "entry_reason": "volume + momentum", "tags": []},
                    {"status": "CLOSED", "symbol": "ETHUSDT", "regime": "TRENDING", "profit_pct": -0.2, "max_profit": 0.1, "exit_reason": "volume_reversal", "exit_type": "early_exit", "entry_reason": "volume + momentum", "tags": []},
                ]
            },
            ttl=3600,
        )
        self.controller.record_regime("TRENDING", 0.8, "system")

        adjusted = self.controller.adjust_weights("system")

        self.assertLess(adjusted["confluence_weight_volume"], self.settings.confluence_weight_volume)
        self.assertGreater(adjusted["confluence_weight_structure"], self.settings.confluence_weight_structure)
        self.assertLess(adjusted["trailing_aggressiveness"], self.settings.trailing_aggressiveness)
        self.assertEqual(adjusted["current_regime"], "TRENDING")
        self.assertGreater(adjusted["capital_allocation_multiplier"], 1.0)
        self.assertEqual(adjusted["symbol_priorities"]["BTCUSDT"], 1.1)
        self.assertEqual(adjusted["symbol_priorities"]["ETHUSDT"], 0.9)
        self.assertGreater(adjusted["symbol_allocations"]["BTCUSDT"], 1.0)

    def test_optimizer_worker_persists_adaptive_config(self):
        self.cache.set_json(
            "analytics:history:system",
            {
                "trades": [
                    {"status": "CLOSED", "symbol": "BTCUSDT", "regime": "RANGING", "profit_pct": 1.0, "max_profit": 1.5, "exit_reason": "structure_break", "exit_type": "early_exit", "entry_reason": "structure + momentum", "tags": ["strict_confluence"]},
                    {"status": "CLOSED", "symbol": "BTCUSDT", "regime": "RANGING", "profit_pct": 1.2, "max_profit": 1.6, "exit_reason": "structure_break", "exit_type": "early_exit", "entry_reason": "structure + momentum", "tags": ["strict_confluence"]},
                    {"status": "CLOSED", "symbol": "BTCUSDT", "regime": "RANGING", "profit_pct": 1.1, "max_profit": 1.7, "exit_reason": "structure_break", "exit_type": "early_exit", "entry_reason": "structure + momentum", "tags": ["strict_confluence"]},
                ]
            },
            ttl=3600,
        )
        self.controller.record_regime("RANGING", 0.7, "system")
        worker = StrategyOptimizerWorker(
            settings=self.settings,
            strategy_controller=self.controller,
        )

        payload = asyncio.run(worker.run_once())

        self.assertIn("updated_at", payload)
        self.assertIsNotNone(self.cache.get_json("strategy:adaptive_config:system"))
        self.assertEqual(payload["current_regime"], "RANGING")

    def test_adjust_weights_respects_cooldown(self):
        current = self.controller.current_config("system")
        current["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.cache.set_json("strategy:adaptive_config:system", current, ttl=3600)

        adjusted = self.controller.adjust_weights("system")

        self.assertTrue(adjusted["cooldown_active"])
        self.assertEqual(adjusted["confluence_weight_structure"], self.settings.confluence_weight_structure)

    def test_adjust_weights_respects_stability_lock(self):
        profitable = []
        for index in range(self.settings.strategy_stability_lock_lookback_trades):
            profitable.append(
                {
                    "status": "CLOSED",
                    "symbol": "BTCUSDT",
                    "regime": "TRENDING",
                    "profit_pct": 1.0 + (index * 0.01),
                    "max_profit": 1.5,
                    "exit_reason": "structure_break",
                    "exit_type": "early_exit",
                    "entry_reason": "structure + momentum",
                    "tags": ["strict_confluence"],
                }
            )
        self.cache.set_json("analytics:history:system", {"trades": profitable}, ttl=3600)

        adjusted = self.controller.adjust_weights("system")

        self.assertTrue(adjusted["stability_lock"])


if __name__ == "__main__":
    unittest.main()
