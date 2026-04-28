import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.retrain_trigger_service import RetrainTriggerService


class InMemoryCache:
    def __init__(self):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ttl=None):
        self.store[key] = value

    def get_json(self, key):
        return self.store.get(key)

    def set_json(self, key, value, ttl=None):
        self.store[key] = value


class StubTradeProbabilityEngine:
    def __init__(self, samples, train_result=None):
        self.samples = samples
        self.train_calls = []
        self.train_result = train_result or {"trained": True, "model_version": "prob-v2"}

    def _load_samples(self):
        return list(self.samples)

    def train(self, samples=None, **kwargs):
        self.train_calls.append(kwargs)
        return dict(self.train_result)


class RetrainTriggerServiceTest(unittest.TestCase):
    def test_emergency_trigger_fires_on_recent_win_rate_breach(self):
        settings = Settings(
            redis_url="redis://unused",
            retrain_recent_trade_window=5,
            retrain_emergency_win_rate_floor=0.4,
            retrain_batch_size=50,
        )
        samples = [
            {"trade_id": f"t{i}", "outcome": value, "closed_at": f"2026-04-{i+1:02d}T00:00:00+00:00"}
            for i, value in enumerate([1, 0, 0, 0, 0])
        ]
        service = RetrainTriggerService(settings=settings, cache=InMemoryCache(), trade_probability_engine=StubTradeProbabilityEngine(samples))

        status = service.evaluate()

        self.assertTrue(status["should_retrain"])
        self.assertEqual(status["trigger_mode"], "emergency")
        self.assertEqual(status["reason"], "recent_win_rate_breach")

    def test_batch_trigger_counts_only_new_closed_samples(self):
        settings = Settings(
            redis_url="redis://unused",
            retrain_recent_trade_window=5,
            retrain_batch_size=3,
        )
        cache = InMemoryCache()
        cache.set("ml:trade_probability:last_processed_sample_at", "2026-04-02T00:00:00+00:00")
        samples = [
            {"trade_id": "t1", "outcome": 1, "closed_at": "2026-04-01T00:00:00+00:00"},
            {"trade_id": "t2", "outcome": 1, "closed_at": "2026-04-03T00:00:00+00:00"},
            {"trade_id": "t3", "outcome": 0, "closed_at": "2026-04-04T00:00:00+00:00"},
            {"trade_id": "t4", "outcome": 1, "closed_at": "2026-04-05T00:00:00+00:00"},
        ]
        service = RetrainTriggerService(settings=settings, cache=cache, trade_probability_engine=StubTradeProbabilityEngine(samples))

        status = service.evaluate()

        self.assertTrue(status["should_retrain"])
        self.assertEqual(status["trigger_mode"], "batch")
        self.assertEqual(status["new_closed_samples"], 3)

    def test_run_if_needed_publishes_notification_after_success(self):
        settings = Settings(
            redis_url="redis://unused",
            retrain_recent_trade_window=3,
            retrain_emergency_win_rate_floor=0.5,
            retrain_recent_validation_trades=3,
            retrain_min_accuracy_lift=0.05,
        )
        cache = InMemoryCache()
        samples = [
            {"trade_id": "t1", "outcome": 0, "closed_at": "2026-04-03T00:00:00+00:00"},
            {"trade_id": "t2", "outcome": 0, "closed_at": "2026-04-04T00:00:00+00:00"},
            {"trade_id": "t3", "outcome": 1, "closed_at": "2026-04-05T00:00:00+00:00"},
        ]
        engine = StubTradeProbabilityEngine(samples)
        service = RetrainTriggerService(settings=settings, cache=cache, trade_probability_engine=engine)

        result = service.run_if_needed()

        self.assertTrue(result["trained"])
        self.assertEqual(engine.train_calls[0]["recent_validation_window"], 3)
        self.assertEqual(engine.train_calls[0]["min_recent_accuracy_lift"], 0.05)
        notice = cache.get_json("ml:trade_probability:last_update_notice")
        self.assertEqual(notice["model_version"], "prob-v2")

    def test_freeze_blocks_retraining_even_when_trigger_conditions_match(self):
        settings = Settings(
            redis_url="redis://unused",
            retrain_recent_trade_window=3,
            retrain_emergency_win_rate_floor=0.5,
        )
        cache = InMemoryCache()
        samples = [
            {"trade_id": "t1", "outcome": 0, "closed_at": "2026-04-03T00:00:00+00:00"},
            {"trade_id": "t2", "outcome": 0, "closed_at": "2026-04-04T00:00:00+00:00"},
            {"trade_id": "t3", "outcome": 1, "closed_at": "2026-04-05T00:00:00+00:00"},
        ]
        engine = StubTradeProbabilityEngine(samples)
        service = RetrainTriggerService(settings=settings, cache=cache, trade_probability_engine=engine)
        service.set_freeze(enabled=True, actor_user_id="admin")

        status = service.evaluate()

        self.assertFalse(status["should_retrain"])
        self.assertEqual(status["reason"], "learning_frozen")
        self.assertTrue(status["freeze_enabled"])

    def test_manual_rollback_cooldown_blocks_retraining(self):
        settings = Settings(
            redis_url="redis://unused",
            retrain_recent_trade_window=3,
            retrain_emergency_win_rate_floor=0.5,
            retrain_manual_rollback_cooldown_hours=48,
        )
        cache = InMemoryCache()
        samples = [
            {"trade_id": "t1", "outcome": 0, "closed_at": "2026-04-03T00:00:00+00:00"},
            {"trade_id": "t2", "outcome": 0, "closed_at": "2026-04-04T00:00:00+00:00"},
            {"trade_id": "t3", "outcome": 1, "closed_at": "2026-04-05T00:00:00+00:00"},
        ]
        engine = StubTradeProbabilityEngine(samples)
        service = RetrainTriggerService(settings=settings, cache=cache, trade_probability_engine=engine)
        service.set_manual_rollback_cooldown(actor_user_id="admin")

        status = service.evaluate()

        self.assertFalse(status["should_retrain"])
        self.assertEqual(status["reason"], "manual_rollback_cooldown")
        self.assertTrue(status["rollback_cooldown_active"])


if __name__ == "__main__":
    unittest.main()
