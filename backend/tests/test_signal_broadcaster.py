import unittest
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.execution_queue_manager import ExecutionQueueManager
from app.services.shard_manager import ShardManager
from app.services.signal_broadcaster import SignalBroadcaster


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


class SignalBroadcasterTest(unittest.TestCase):
    def test_publish_signal_versions_and_filters_subscribers(self):
        settings = Settings(redis_url="redis://unused", execution_shard_count=4)
        cache = InMemoryCache()
        shard_manager = ShardManager(settings)
        queue_manager = ExecutionQueueManager(settings, cache, shard_manager)
        broadcaster = SignalBroadcaster(settings, cache, queue_manager)

        broadcaster.register_subscription("u-free", tier="free", balance=20.0, risk_profile="conservative")
        broadcaster.register_subscription("u-pro", tier="pro", balance=500.0, risk_profile="moderate")
        broadcaster.register_subscription("u-vip", tier="vip", balance=5_000.0, risk_profile="aggressive")

        published = broadcaster.publish_signal(
            {
                "signal_id": "sig-1",
                "symbol": "BTCUSDT",
                "strategy": "TREND_FOLLOW",
                "alpha_decision": {"final_score": 85.0},
                "required_tier": "pro",
                "min_balance": 100.0,
                "allowed_risk_profiles": ["moderate", "aggressive"],
            }
        )

        self.assertEqual(published["signal_version"], 1)
        self.assertEqual(published["distribution"]["eligible_subscribers"], 2)
        self.assertEqual(published["distribution"]["queued_total"], 2)
        self.assertIn("pub:signals:central", cache.store)
        self.assertIn("pub:signals:fanout", cache.store)


if __name__ == "__main__":
    unittest.main()
