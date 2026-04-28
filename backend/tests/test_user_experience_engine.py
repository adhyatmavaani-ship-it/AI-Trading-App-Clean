import json
import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.user_experience_engine import UserExperienceEngine


class InMemoryCache:
    def __init__(self):
        self.store = {}
        self.messages = []

    def get_json(self, key):
        return self.store.get(key)

    def set_json(self, key, value, ttl):
        self.store[key] = value

    def publish(self, channel, message):
        self.messages.append((channel, json.loads(message)))
        return 1


class UserExperienceEngineTest(unittest.TestCase):
    def test_publish_activity_updates_latest_and_history(self):
        cache = InMemoryCache()
        engine = UserExperienceEngine(Settings(redis_url="redis://unused"), cache)

        payload = engine.publish_activity(
            status="scanning",
            message="BTC checked -> weak volume, skipped",
            bot_state="SCANNING",
            symbol="BTCUSDT",
            next_scan="ETHUSDT",
            confidence=0.42,
            intent="Watching BTC for stronger volume",
            readiness=41.0,
            reason="weak volume",
            extra={
                "confluence_breakdown": {
                    "rsi": "Oversold rebound",
                    "volume": "Volume spiking",
                },
                "confluence_aligned": 2,
                "confluence_total": 5,
                "risk_flags": {
                    "volatility": "Contained",
                    "spread": "Tight",
                    "liquidity_warning": False,
                },
                "logic_tags": ["#MeanReversion", "#BreakoutHunter"],
            },
        )

        self.assertEqual(engine.latest()["status"], "scanning")
        self.assertEqual(engine.history(limit=10)[-1]["symbol"], "BTCUSDT")
        self.assertEqual(cache.messages[-1][0], engine.settings.live_activity_channel)
        self.assertEqual(payload["bot_state"], "SCANNING")
        self.assertEqual(engine.readiness(limit=10)[0]["symbol"], "BTCUSDT")
        self.assertEqual(engine.readiness(limit=10)[0]["readiness"], 41.0)
        self.assertEqual(
            engine.readiness(limit=10)[0]["confluence_breakdown"]["rsi"],
            "Oversold rebound",
        )
        self.assertFalse(engine.readiness(limit=10)[0]["risk_flags"]["liquidity_warning"])
        self.assertEqual(engine.readiness(limit=10)[0]["logic_tags"][0], "#MeanReversion")


if __name__ == "__main__":
    unittest.main()
