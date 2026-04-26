import time
import unittest
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.execution_queue_manager import ExecutionQueueManager
from app.services.shard_manager import ShardManager


class InMemoryCache:
    def __init__(self):
        self.store = {}

    def get_json(self, key):
        return self.store.get(key)

    def set_json(self, key, value, ttl):
        self.store[key] = value

    def increment(self, key, ttl):
        self.store[key] = int(self.store.get(key, 0)) + 1
        return self.store[key]

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ttl=None):
        self.store[key] = value

    def set_if_absent(self, key, value, ttl):
        if key in self.store:
            return False
        self.store[key] = value
        return True

    def delete(self, key):
        self.store.pop(key, None)

    def publish(self, channel, message):
        self.store[f"pub:{channel}"] = message
        return 1

    def keys(self, pattern):
        prefix = pattern.replace("*", "")
        return [key for key in self.store if key.startswith(prefix)]

    def zadd_json(self, key, score, value):
        self.store.setdefault(key, []).append((score, value))

    def zpop_due_json(self, key, max_score, limit=100):
        entries = sorted(self.store.get(key, []), key=lambda item: item[0])
        due_entries = [(score, value) for score, value in entries if score <= max_score]
        due = [value for _, value in due_entries[:limit]]
        self.store[key] = due_entries[limit:] + [(score, value) for score, value in entries if score > max_score]
        return due

    def zcard(self, key):
        return len(self.store.get(key, []))


class ExecutionQueueManagerTest(unittest.TestCase):
    def test_enqueue_and_dequeue_jobs_by_priority_and_shard(self):
        settings = Settings(
            redis_url="redis://unused",
            execution_shard_count=2,
            randomized_execution_delay_min_ms=0,
            randomized_execution_delay_max_ms=0,
            delayed_queue_min_ms=0,
            delayed_queue_max_ms=0,
        )
        cache = InMemoryCache()
        shard_manager = ShardManager(settings)
        queue_manager = ExecutionQueueManager(settings, cache, shard_manager)

        summary = queue_manager.enqueue_signal(
            {"signal_id": "sig-1", "symbol": "ETHUSDT", "strategy": "BREAKOUT", "alpha_decision": {"final_score": 92.0}},
            [
                {"user_id": "u1", "tier": "vip", "balance": 1_000.0, "risk_profile": "aggressive"},
                {"user_id": "u2", "tier": "free", "balance": 500.0, "risk_profile": "moderate"},
            ],
        )

        self.assertEqual(summary["queued_total"], 2)
        self.assertEqual(summary["queue_counts"]["high"], 1)
        self.assertEqual(summary["queue_counts"]["delayed"], 1)

        time.sleep(0.02)
        due_jobs = []
        for shard_id in range(settings.execution_shard_count):
            due_jobs.extend(queue_manager.dequeue_batch(shard_id, limit=10))

        self.assertEqual(len(due_jobs), 2)
        self.assertEqual({job["user_id"] for job in due_jobs}, {"u1", "u2"})

    def test_throttle_adds_backoff_after_burst(self):
        settings = Settings(redis_url="redis://unused", execution_rate_limit_per_second=2)
        cache = InMemoryCache()
        queue_manager = ExecutionQueueManager(settings, cache, ShardManager(settings))

        first = queue_manager.throttle("binance")
        second = queue_manager.throttle("binance")
        third = queue_manager.throttle("binance")

        self.assertEqual(first, 0.0)
        self.assertEqual(second, 0.0)
        self.assertGreater(third, 0.0)

    def test_strong_sleeve_budget_pressure_upgrades_queue_priority(self):
        settings = Settings(redis_url="redis://unused", high_priority_alpha_threshold=95.0)
        shard_manager = ShardManager(settings)

        priority = shard_manager.queue_priority(
            {
                "alpha_decision": {"final_score": 84.0},
                "trade_success_probability": 0.68,
                "factor_sleeve_budget_delta": 0.10,
                "factor_sleeve_recent_win_rate": 0.61,
            },
            {"user_id": "u1", "tier": "vip", "risk_profile": "moderate"},
        )

        self.assertEqual(priority, "high")

    def test_unstable_sleeve_rotation_does_not_flip_queue_priority(self):
        settings = Settings(
            redis_url="redis://unused",
            high_priority_alpha_threshold=95.0,
            portfolio_concentration_soft_turnover=0.20,
        )
        shard_manager = ShardManager(settings)

        priority = shard_manager.queue_priority(
            {
                "alpha_decision": {"final_score": 84.0},
                "trade_success_probability": 0.68,
                "factor_sleeve_budget_delta": 0.10,
                "factor_sleeve_recent_win_rate": 0.61,
                "factor_sleeve_budget_turnover": 0.25,
                "max_factor_sleeve_budget_gap_pct": 0.03,
            },
            {"user_id": "u1", "tier": "vip", "risk_profile": "moderate"},
        )

        self.assertEqual(priority, "normal")


if __name__ == "__main__":
    unittest.main()
