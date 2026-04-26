import asyncio
import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.narrative_macro_intelligence import NarrativeMacroIntelligenceEngine
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


class StubFirestore:
    def __init__(self):
        self.updated = {}
        self.snapshots = {}

    def update_trade(self, trade_id, payload):
        self.updated[trade_id] = payload

    def save_performance_snapshot(self, user_id, payload):
        self.snapshots[user_id] = payload


class NarrativeMacroIntelligenceTest(unittest.TestCase):
    def setUp(self):
        self.cache = InMemoryCache()
        self.firestore = StubFirestore()
        self.settings = Settings(model_dir=str(Path.cwd() / "tmp-macro-intel"), redis_url="redis://unused")
        self.redis_state_manager = RedisStateManager(self.settings, self.cache)
        self.engine = NarrativeMacroIntelligenceEngine(
            settings=self.settings,
            redis_state_manager=self.redis_state_manager,
            firestore=self.firestore,
        )

    def test_bubble_risk_tightens_active_trade_stops(self):
        self.redis_state_manager.save_active_trade(
            "trade-1",
            {
                "trade_id": "trade-1",
                "user_id": "user-1",
                "symbol": "SOLUSDT",
                "side": "BUY",
                "entry": 150.0,
                "stop_loss": 144.0,
                "trailing_stop_pct": 0.01,
                "status": "FILLED",
            },
        )

        report = asyncio.run(
            self.engine.analyze_market(
                symbol="SOLUSDT",
                social_metrics={
                    "hype_score": 0.91,
                    "velocity_score": 0.88,
                    "dispersion_score": 0.74,
                    "influencer_concentration": 0.85,
                },
                onchain_metrics={
                    "buy_volume_score": 0.24,
                    "buy_volume_trend": -0.31,
                    "whale_participation": 0.22,
                    "exchange_inflow_risk": 0.76,
                    "stablecoin_support": 0.28,
                },
                macro_metrics={
                    "dxy_1h_return": 0.011,
                    "spx_1h_return": -0.012,
                    "nasdaq_1h_return": -0.021,
                    "gold_1h_return": 0.004,
                    "us10y_1h_change_bps": 7.5,
                    "safe_haven_rotation": 0.82,
                    "risk_off_spillover": 0.88,
                    "inflation_hedge_pressure": 0.71,
                    "liquidity_drain_score": 0.84,
                    "macro_bearish_score": 0.86,
                },
            )
        )

        self.assertTrue(report["bubble_risk"]["signal"])
        self.assertGreater(report["divergence_score"]["divergence_score"], 0.6)
        updated_trade = self.redis_state_manager.load_active_trade("trade-1")
        self.assertLess(updated_trade["trailing_stop_pct"], 0.01)
        self.assertGreater(updated_trade["stop_loss"], 144.0)
        self.assertEqual(updated_trade["risk_overlay"], "BUBBLE_RISK")
        self.assertIn("trade-1", self.firestore.updated)

    def test_no_bubble_risk_leaves_stops_unchanged(self):
        self.redis_state_manager.save_active_trade(
            "trade-2",
            {
                "trade_id": "trade-2",
                "user_id": "user-2",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "entry": 100000.0,
                "stop_loss": 97000.0,
                "trailing_stop_pct": 0.004,
                "status": "FILLED",
            },
        )

        report = asyncio.run(
            self.engine.analyze_market(
                symbol="BTCUSDT",
                social_metrics={
                    "hype_score": 0.42,
                    "velocity_score": 0.38,
                    "dispersion_score": 0.20,
                    "influencer_concentration": 0.25,
                },
                onchain_metrics={
                    "buy_volume_score": 0.68,
                    "buy_volume_trend": 0.18,
                    "whale_participation": 0.64,
                    "exchange_inflow_risk": 0.22,
                    "stablecoin_support": 0.66,
                },
                macro_metrics={
                    "dxy_1h_return": -0.002,
                    "spx_1h_return": 0.005,
                    "nasdaq_1h_return": 0.007,
                    "gold_1h_return": 0.001,
                    "us10y_1h_change_bps": -1.0,
                    "safe_haven_rotation": 0.18,
                    "risk_off_spillover": 0.14,
                    "inflation_hedge_pressure": 0.22,
                    "liquidity_drain_score": 0.20,
                    "macro_bearish_score": 0.16,
                },
            )
        )

        self.assertFalse(report["bubble_risk"]["signal"])
        unchanged_trade = self.redis_state_manager.load_active_trade("trade-2")
        self.assertEqual(unchanged_trade["trailing_stop_pct"], 0.004)
        self.assertEqual(unchanged_trade["stop_loss"], 97000.0)

    def test_historical_matches_are_returned_without_pinecone(self):
        report = asyncio.run(
            self.engine.analyze_market(
                symbol="ETHUSDT",
                social_metrics={
                    "hype_score": 0.80,
                    "velocity_score": 0.75,
                    "dispersion_score": 0.55,
                    "influencer_concentration": 0.70,
                },
                onchain_metrics={
                    "buy_volume_score": 0.33,
                    "buy_volume_trend": -0.12,
                    "whale_participation": 0.28,
                    "exchange_inflow_risk": 0.58,
                    "stablecoin_support": 0.34,
                },
                macro_metrics={
                    "dxy_1h_return": 0.008,
                    "spx_1h_return": -0.010,
                    "nasdaq_1h_return": -0.018,
                    "gold_1h_return": 0.002,
                    "us10y_1h_change_bps": 6.2,
                    "safe_haven_rotation": 0.74,
                    "risk_off_spillover": 0.80,
                    "inflation_hedge_pressure": 0.67,
                    "liquidity_drain_score": 0.76,
                    "macro_bearish_score": 0.79,
                },
            )
        )

        self.assertEqual(len(report["historical_matches"]), 3)
        self.assertIn("name", report["historical_matches"][0])
        self.assertIn("similarity", report["historical_matches"][0])


if __name__ == "__main__":
    unittest.main()
