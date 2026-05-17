import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.adaptive_learning import AdaptiveLearningService


class InMemoryCache:
    def __init__(self):
        self.store = {}

    def get_json(self, key):
        return self.store.get(key)

    def set_json(self, key, value, ttl):
        self.store[key] = value


class StubFirestore:
    def __init__(self):
        self.snapshots = []

    def save_performance_snapshot(self, user_id, payload):
        self.snapshots.append((user_id, payload))


class FailingCache(InMemoryCache):
    def set_json(self, key, value, ttl):
        raise RuntimeError("cache unavailable")


class FailingFirestore(StubFirestore):
    def save_performance_snapshot(self, user_id, payload):
        raise RuntimeError("firestore unavailable")


class AdaptiveLearningServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.cache = InMemoryCache()
        self.firestore = StubFirestore()
        self.settings = Settings(redis_url="redis://unused", model_dir=self.tmpdir.name)
        self.service = AdaptiveLearningService(
            settings=self.settings,
            cache=self.cache,
            firestore=self.firestore,
        )
        self.feature_snapshot = {
            "regime": "TRENDING",
            "price": 100.0,
            "atr": 1.0,
            "5m_rsi": 62.0,
            "15m_ema_spread": 0.004,
        }

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_losing_pattern_is_blacklisted_after_repeated_losses(self):
        active_trade = {
            "side": "BUY",
            "feature_snapshot": dict(self.feature_snapshot),
        }

        for index in range(4):
            report = self.service.record_trade_outcome(
                trade_id=f"loss-{index}",
                active_trade=active_trade,
                pnl=-12.5,
            )

        self.assertTrue(report["blacklisted"])
        feedback = self.service.evaluate_signal(
            symbol="BTCUSDT",
            side="BUY",
            strategy="HYBRID_TREND_PULLBACK",
            feature_snapshot=dict(self.feature_snapshot),
        )
        self.assertTrue(feedback.block_trade)
        self.assertLess(feedback.confidence_multiplier, 1.0)
        self.assertGreaterEqual(len(self.firestore.snapshots), 1)

    def test_winning_pattern_is_whitelisted_and_boosted(self):
        active_trade = {
            "side": "SELL",
            "feature_snapshot": {
                **self.feature_snapshot,
                "regime": "RANGING",
                "5m_rsi": 41.0,
            },
        }

        for index in range(4):
            report = self.service.record_trade_outcome(
                trade_id=f"win-{index}",
                active_trade=active_trade,
                pnl=9.0,
            )

        self.assertTrue(report["whitelisted"])
        feedback = self.service.evaluate_signal(
            symbol="ETHUSDT",
            side="SELL",
            strategy="RSI_REVERSION",
            feature_snapshot=dict(active_trade["feature_snapshot"]),
        )
        self.assertFalse(feedback.block_trade)
        self.assertGreater(feedback.confidence_multiplier, 1.0)
        snapshot = self.service.snapshot()
        self.assertIn("RANGING", snapshot["regimes"])
        self.assertGreaterEqual(snapshot["whitelist_total"], 1)

    def test_corrupt_cached_state_falls_back_to_default_memory(self):
        self.cache.store[self.service.cache_key] = ["not", "a", "state"]

        feedback = self.service.evaluate_signal(
            symbol="BTCUSDT",
            side="BUY",
            strategy="HYBRID_TREND_PULLBACK",
            feature_snapshot=dict(self.feature_snapshot),
        )

        self.assertFalse(feedback.block_trade)
        self.assertEqual(feedback.trades, 0)
        self.assertEqual(feedback.regime, "TRENDING")

    def test_persistence_failures_do_not_block_outcome_learning_report(self):
        service = AdaptiveLearningService(
            settings=self.settings,
            cache=FailingCache(),
            firestore=FailingFirestore(),
        )

        report = service.record_trade_outcome(
            trade_id="safe-close-1",
            active_trade={
                "side": "BUY",
                "feature_snapshot": dict(self.feature_snapshot),
            },
            pnl=-5.0,
        )

        self.assertEqual(report["trades"], 1)
        self.assertFalse(report["blacklisted"])


if __name__ == "__main__":
    unittest.main()
