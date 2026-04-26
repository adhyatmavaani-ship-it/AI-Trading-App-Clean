import asyncio
import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.dual_track_engine import DualTrackCoordinator
from app.services.feature_pipeline import FeaturePipeline
from app.services.redis_state_manager import RedisStateManager


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
        return 1

    def keys(self, pattern):
        prefix = pattern.replace("*", "")
        return [key for key in self.store if key.startswith(prefix)]


class StubDrawdownProtection:
    class State:
        current_equity = 10000.0

    def load(self, user_id):
        return self.State()


class StubMarketData:
    async def fetch_multi_timeframe_ohlcv(self, symbol, intervals=("1m", "5m", "15m")):
        import pandas as pd

        def frame(values, volumes):
            return pd.DataFrame(
                {
                    "open": values,
                    "high": [value * 1.001 for value in values],
                    "low": [value * 0.999 for value in values],
                    "close": values,
                    "volume": volumes,
                }
            )

        uptrend = [100 + idx * 0.2 for idx in range(40)]
        strong_volume = [1000 + idx * 30 for idx in range(40)]
        return {
            "1m": frame(uptrend, strong_volume),
            "5m": frame(uptrend, strong_volume),
            "15m": frame(uptrend, strong_volume),
        }

    async def fetch_order_book(self, symbol):
        return {
            "bids": [{"price": 107.9, "qty": 25.0} for _ in range(10)],
            "asks": [{"price": 108.1, "qty": 10.0} for _ in range(10)],
        }

    async def fetch_latest_price(self, symbol):
        return 108.0


class StubSentimentEngine:
    async def analyze_token(self, symbol, market_features):
        return {"hype_score": 0.8, "buzz_score": 0.72, "volume_alignment": 0.55}


class StubWhaleTracker:
    async def evaluate_token(self, symbol, chain, market_features):
        return {"score": 0.68}


class StubLiquidityMonitor:
    async def assess_token(self, symbol, chain, market_features):
        return {"liquidity_stability": 0.74, "rug_pull_risk": 0.18}


class StubMultiChainRouter:
    def route(self, symbol, side, requested_notional):
        return {"chain": "ethereum"}


class StubNarrativeMacro:
    async def fetch_macro_context(self):
        return {
            "macro_metrics": {
                "dxy_1h_return": 0.008,
                "spx_1h_return": -0.006,
                "nasdaq_1h_return": -0.011,
                "gold_1h_return": 0.002,
                "us10y_1h_change_bps": 5.0,
                "safe_haven_rotation": 0.72,
                "risk_off_spillover": 0.66,
                "risk_on_spillover": 0.14,
                "inflation_hedge_pressure": 0.44,
                "liquidity_drain_score": 0.70,
                "macro_bearish_score": 0.69,
            }
        }

    async def analyze_market(self, *, symbol, social_metrics, onchain_metrics, macro_metrics):
        return {
            "macro_bias": {
                "regime": "BEARISH",
                "multiplier": 0.5,
                "reason": "Macro stress",
                "updated_at": "2026-01-01T00:00:00Z",
            }
        }


class DualTrackCoordinatorTest(unittest.TestCase):
    def setUp(self):
        settings = Settings(redis_url="redis://unused", model_dir=str(Path.cwd() / "tmp-dual-track"))
        self.cache = InMemoryCache()
        self.coordinator = DualTrackCoordinator(
            settings=settings,
            cache=self.cache,
            market_data=StubMarketData(),
            feature_pipeline=FeaturePipeline(),
            sentiment_engine=StubSentimentEngine(),
            whale_tracker=StubWhaleTracker(),
            liquidity_monitor=StubLiquidityMonitor(),
            multi_chain_router=StubMultiChainRouter(),
            drawdown_protection=StubDrawdownProtection(),
            narrative_macro_intelligence=StubNarrativeMacro(),
        )
        self.redis_state_manager = RedisStateManager(settings, self.cache)

    def test_sniper_respects_cached_bearish_bias(self):
        self.cache.set_json(
            "dual_track:bias:BTCUSDT",
            {"regime": "BEARISH", "multiplier": 0.5, "reason": "risk off", "updated_at": "now"},
            ttl=60,
        )

        decision = asyncio.run(self.coordinator.sniper_decision(user_id="u1", symbol="BTCUSDT"))

        self.assertEqual(decision.market_bias["regime"], "BEARISH")
        self.assertIn(decision.action, {"SELL", "HOLD"})
        if decision.action != "HOLD":
            self.assertLessEqual(decision.requested_notional, 75.0)

    def test_warmup_caches_execution_context(self):
        payload = asyncio.run(self.coordinator.warmup_execution_context(user_id="u1", symbol="ETHUSDT"))

        self.assertEqual(payload["symbol"], "ETHUSDT")
        self.assertIn("latest_price", payload)
        self.assertIsNotNone(self.cache.get_json("warmup:u1:ETHUSDT"))

    def test_brain_refresh_stores_bias(self):
        bias = asyncio.run(self.coordinator.refresh_brain_bias("SOLUSDT"))

        self.assertEqual(bias["regime"], "BEARISH")
        self.assertEqual(self.cache.get_json("dual_track:bias:SOLUSDT")["multiplier"], 0.5)

    def test_sniper_uses_symbol_threshold_overrides(self):
        self.cache.set_json(
            "dual_track:bias:BTCUSDT",
            {"regime": "BEARISH", "multiplier": 0.5, "reason": "risk off", "updated_at": "now"},
            ttl=60,
        )
        self.cache.set_json(
            "dual_track:thresholds:BTCUSDT",
            {
                "long_entry_rsi": 90.0,
                "long_confirmation_rsi": 85.0,
                "short_entry_rsi": 40.0,
                "short_confirmation_rsi": 45.0,
            },
            ttl=60,
        )

        decision = asyncio.run(self.coordinator.sniper_decision(user_id="u1", symbol="BTCUSDT"))

        self.assertEqual(decision.action, "HOLD")


if __name__ == "__main__":
    unittest.main()
