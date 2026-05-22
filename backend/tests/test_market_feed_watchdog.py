from __future__ import annotations

from datetime import datetime, timezone
import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings  # noqa: E402
from app.services.market_feed_watchdog import MarketFeedWatchdog  # noqa: E402
from app.services.redis_cache import RedisCache  # noqa: E402


class MarketFeedWatchdogTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cache = RedisCache("")
        self.watchdog = MarketFeedWatchdog(
            Settings(
                redis_url="",
                market_feed_min_stale_seconds=180.0,
                market_feed_stale_multiplier=3.0,
                market_feed_max_volume_spike_ratio=20.0,
            ),
            self.cache,
        )

    def _frame(self, *, age_seconds: float = 30.0, frozen: bool = False, volume: float = 100.0) -> pd.DataFrame:
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        step_ms = 60_000
        rows = []
        for index in range(24):
            close_time = now_ms - int(age_seconds * 1000) - ((23 - index) * step_ms)
            if frozen and index >= 21:
                close_time = rows[-1]["close_time"]
            rows.append(
                {
                    "open_time": close_time - step_ms,
                    "close_time": close_time,
                    "close": 100.0 + index,
                    "volume": volume if index == 23 else 100.0,
                }
            )
        return pd.DataFrame(rows)

    def test_healthy_frame_updates_feed_state(self):
        health = self.watchdog.evaluate_frame("btcusdt", "1m", self._frame())

        self.assertTrue(health.healthy)
        self.assertEqual(health.status, "healthy")
        self.assertIsNotNone(self.cache.get("market:feed:last_seen_ts"))
        cached = self.cache.get_json("market:feed:health")
        self.assertEqual(cached["symbol"], "BTCUSDT")
        self.assertTrue(cached["healthy"])

    def test_stale_frame_is_marked_unhealthy(self):
        health = self.watchdog.evaluate_frame("ETHUSDT", "1m", self._frame(age_seconds=600.0))

        self.assertFalse(health.healthy)
        self.assertIn("market feed stale", health.reasons)
        self.assertEqual(int(self.cache.get("monitor:websocket_stale_feed_count") or 0), 1)

    def test_frozen_timestamp_and_impossible_volume_spike_are_detected(self):
        health = self.watchdog.evaluate_frame(
            "SOLUSDT",
            "1m",
            self._frame(frozen=True, volume=5_000.0),
        )

        self.assertFalse(health.healthy)
        self.assertIn("frozen candle timestamps", health.reasons)
        self.assertIn("impossible volume spike", health.reasons)


if __name__ == "__main__":
    unittest.main()
