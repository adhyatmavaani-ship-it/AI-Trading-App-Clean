import unittest
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.analytics_service import AnalyticsService
from app.services.redis_state_manager import RedisStateManager


class InMemoryCache:
    def __init__(self):
        self.store = {}

    def get_json(self, key):
        return self.store.get(key)

    def set_json(self, key, value, ttl):
        self.store[key] = value

    def keys(self, pattern):
        prefix = pattern.replace("*", "")
        return [key for key in self.store if key.startswith(prefix)]

    def delete(self, key):
        self.store.pop(key, None)


class StubFirestore:
    def __init__(self):
        self.snapshots = []

    def save_performance_snapshot(self, user_id, payload):
        self.snapshots.append((user_id, payload))


class AnalyticsServiceTest(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(redis_url="redis://unused")
        self.cache = InMemoryCache()
        self.redis_state_manager = RedisStateManager(self.settings, self.cache)
        self.firestore = StubFirestore()
        self.service = AnalyticsService(
            settings=self.settings,
            cache=self.cache,
            redis_state_manager=self.redis_state_manager,
            firestore=self.firestore,
        )

    def test_summary_calculates_expectancy_and_profit_factor(self):
        self.cache.set_json(
            "analytics:history:u1",
            {
                "trades": [
                    {"status": "CLOSED", "symbol": "BTCUSDT", "regime": "TRENDING", "profit_pct": 2.0, "max_profit": 2.4, "exit_reason": "structure_break", "exit_type": "early_exit", "entry_reason": "structure + momentum", "tags": []},
                    {"status": "CLOSED", "symbol": "ETHUSDT", "regime": "RANGING", "profit_pct": -1.0, "max_profit": 0.2, "exit_reason": "volume_reversal", "exit_type": "early_exit", "entry_reason": "momentum + volume", "tags": ["mfi_divergence"]},
                    {"status": "CLOSED", "symbol": "BTCUSDT", "regime": "TRENDING", "profit_pct": 1.0, "max_profit": 1.8, "exit_reason": "stop_loss_hit", "exit_type": "stop_loss", "entry_reason": "structure + momentum", "tags": []},
                ]
            },
            ttl=3600,
        )

        summary = self.service.summary("u1")

        self.assertEqual(summary["trades"], 3)
        self.assertAlmostEqual(summary["win_rate"], 2 / 3, places=6)
        self.assertAlmostEqual(summary["avg_win"], 1.5, places=6)
        self.assertAlmostEqual(summary["avg_loss"], 1.0, places=6)
        self.assertAlmostEqual(summary["profit_factor"], 3.0, places=6)
        self.assertAlmostEqual(summary["expectancy"], (2 / 3 * 1.5) - (1 / 3 * 1.0), places=6)
        self.assertEqual(summary["best_symbols"][0], "BTCUSDT")
        self.assertEqual(summary["best_regime"], "TRENDING")
        self.assertEqual(summary["worst_regime"], "RANGING")
        self.assertAlmostEqual(summary["regime_win_rates"]["TRENDING"], 1.0, places=6)
        self.assertEqual(summary["most_profitable_setup"], "structure + momentum")

    def test_performance_generates_feedback_insights(self):
        self.cache.set_json(
            "analytics:history:u1",
            {
                "trades": [
                    {"status": "CLOSED", "regime": "RANGING", "profit_pct": -1.4, "max_profit": 0.3, "exit_reason": "volume_reversal", "exit_type": "early_exit", "tags": ["mfi_divergence"]},
                    {"status": "CLOSED", "regime": "RANGING", "profit_pct": -0.8, "max_profit": 0.1, "exit_reason": "volume_reversal", "exit_type": "early_exit", "tags": ["mfi_divergence"]},
                    {"status": "CLOSED", "regime": "RANGING", "profit_pct": -0.5, "max_profit": 0.2, "exit_reason": "volume_reversal", "exit_type": "early_exit", "tags": ["mfi_divergence"]},
                    {"status": "CLOSED", "regime": "TRENDING", "profit_pct": 0.4, "max_profit": 2.2, "exit_reason": "structure_break", "exit_type": "early_exit", "tags": []},
                ]
            },
            ttl=3600,
        )

        payload = self.service.performance("u1")

        self.assertIn("weights", payload)
        self.assertIn("feedback", payload)
        self.assertIn("volume spike exits = mostly loss -> entry filter weak", payload["feedback"]["insights"])
        self.assertIn("MFI divergence trades = low win rate", payload["feedback"]["insights"])

    def test_feedback_exposes_symbol_intelligence_and_false_signal_rate(self):
        self.cache.set_json(
            "analytics:history:u1",
            {
                "trades": [
                    {"status": "CLOSED", "symbol": "BTCUSDT", "regime": "TRENDING", "profit_pct": 1.3, "max_profit": 2.0, "exit_reason": "structure_break", "exit_type": "early_exit", "entry_reason": "structure + momentum", "tags": ["strict_confluence"]},
                    {"status": "CLOSED", "symbol": "BTCUSDT", "regime": "TRENDING", "profit_pct": 0.8, "max_profit": 1.2, "exit_reason": "structure_break", "exit_type": "early_exit", "entry_reason": "structure + momentum", "tags": ["strict_confluence"]},
                    {"status": "CLOSED", "symbol": "ETHUSDT", "regime": "RANGING", "profit_pct": -0.4, "max_profit": 0.2, "exit_reason": "volume_reversal", "exit_type": "early_exit", "entry_reason": "volume + momentum", "tags": []},
                    {"status": "CLOSED", "symbol": "ETHUSDT", "regime": "RANGING", "profit_pct": -0.3, "max_profit": 0.1, "exit_reason": "volume_reversal", "exit_type": "early_exit", "entry_reason": "volume + momentum", "tags": []},
                ]
            },
            ttl=3600,
        )

        feedback = self.service.get_feedback("u1")

        self.assertIn("symbol_performance", feedback)
        self.assertEqual(feedback["best_symbols"][0], "BTCUSDT")
        self.assertEqual(feedback["best_regime"], "TRENDING")
        self.assertGreater(feedback["false_signal_rate"], 0.0)

    def test_summary_includes_portfolio_metrics(self):
        self.redis_state_manager.save_active_trade(
            "t-open",
            {
                "trade_id": "t-open",
                "user_id": "u1",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "entry": 100.0,
                "executed_quantity": 10.0,
                "risk_fraction": 0.01,
                "portfolio_correlation_risk": 0.8,
                "regime": "TRENDING",
            },
        )
        self.cache.set_json(
            "analytics:history:u1",
            {
                "trades": [
                    {"status": "CLOSED", "symbol": "BTCUSDT", "regime": "TRENDING", "profit_pct": 1.0, "max_profit": 1.5, "exit_reason": "structure_break", "exit_type": "early_exit", "entry_reason": "structure + momentum", "tags": []},
                    {"status": "CLOSED", "symbol": "ETHUSDT", "regime": "HIGH_VOL", "profit_pct": -0.5, "max_profit": 0.2, "exit_reason": "volume_reversal", "exit_type": "early_exit", "entry_reason": "momentum + volume", "tags": []},
                ]
            },
            ttl=3600,
        )

        summary = self.service.summary("u1")

        self.assertGreater(summary["capital_utilization"], 0.0)
        self.assertAlmostEqual(summary["risk_exposure"], 0.01, places=6)
        self.assertAlmostEqual(summary["correlation_risk"], 0.8, places=6)
        self.assertIn("TRENDING", summary["regime_distribution"])

    def test_record_closed_trade_persists_history_and_snapshots(self):
        active_trade = {
            "trade_id": "t1",
            "user_id": "u1",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "entry": 100.0,
            "max_profit": 0.028,
            "entry_reason": "Structure breakout + MFI momentum + volume confirmation",
            "regime": "TRENDING",
            "created_at": "2026-01-01T00:00:00+00:00",
            "feature_snapshot": {"strict_trade_allowed": 1.0},
        }
        close_payload = {"realized_pnl": 12.0, "status": "CLOSED"}

        record = self.service.record_closed_trade(
            user_id="u1",
            trade_id="t1",
            active_trade=active_trade,
            close_payload=close_payload,
            exit_price=101.25,
            exit_reason="structure_break",
            exit_type="early_exit",
        )

        history = self.service.trade_history("u1", limit=10)
        self.assertEqual(len(history), 1)
        self.assertEqual(record["profit_pct"], 1.25)
        self.assertEqual(record["regime"], "TRENDING")
        self.assertAlmostEqual(record["max_profit"], 2.8, places=6)
        self.assertEqual(record["training_label"], 1)
        self.assertTrue(record["is_profit"])
        self.assertEqual(record["feature_snapshot"]["strict_trade_allowed"], 1.0)
        self.assertTrue(self.firestore.snapshots)


if __name__ == "__main__":
    unittest.main()
