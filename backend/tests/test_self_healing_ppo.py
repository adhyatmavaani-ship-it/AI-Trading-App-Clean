import json
import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.self_healing_ppo import RewardProfile, SelfHealingPPOService


class InMemoryCache:
    def __init__(self):
        self.store = {}

    def get_json(self, key):
        return self.store.get(key)

    def set_json(self, key, payload, ttl=None):
        self.store[key] = payload

    def keys(self, pattern):
        prefix = pattern.replace("*", "")
        return [key for key in self.store if key.startswith(prefix)]


class StubFirestore:
    def __init__(self):
        self.snapshots = {}

    def save_performance_snapshot(self, user_id, payload):
        self.snapshots[user_id] = payload


class StubPPOModel:
    def set_env(self, env):
        self.env = env

    def learn(self, total_timesteps, progress_bar=False):
        return self

    def predict(self, observation, deterministic=True):
        return [0.8, 0.9, 0.4], None

    def save(self, path):
        return None


class TestableSelfHealingPPOService(SelfHealingPPOService):
    def _load_or_create_model(self, env):
        return StubPPOModel()


class SelfHealingPPOServiceTest(unittest.TestCase):
    def test_loss_event_generates_post_mortem_and_updates_reward_profile(self):
        artifacts = Path.cwd() / "tmp-self-healing-tests"
        settings = Settings(model_dir=str(artifacts), redis_url="redis://unused")
        cache = InMemoryCache()
        firestore = StubFirestore()
        service = TestableSelfHealingPPOService(settings=settings, cache=cache, firestore=firestore)

        report = service.handle_trade_outcome(
            trade_id="trade-loss-1",
            active_trade={
                "symbol": "BTCUSDT",
                "side": "BUY",
                "status": "FILLED",
                "notional": 1000.0,
                "confidence": 0.88,
                "expected_return": 0.012,
                "expected_risk": 0.045,
                "actual_slippage_bps": 62.0,
                "feature_snapshot": {
                    "15m_volume": 120000.0,
                    "1m_return": 0.008,
                    "5m_return": 0.015,
                    "order_book_imbalance": 0.34,
                },
                "regime_confidence": 0.81,
            },
            pnl=-42.0,
        )

        self.assertIsNotNone(report)
        self.assertEqual(report["trade_id"], "trade-loss-1")
        self.assertIn("feature_importance", report)
        self.assertIn("reward_adjustment", report)
        self.assertGreater(report["reward_adjustment"]["after"]["volatility_penalty"], 1.0)
        self.assertGreater(report["reward_adjustment"]["after"]["low_volume_penalty"], 1.0)
        self.assertIn("thin session volume", report["confidence_diagnosis"]["why_confidence_was_wrong"])

        saved_profile = json.loads((artifacts / "self_healing_reward_profile.json").read_text(encoding="utf-8"))
        self.assertEqual(
            saved_profile["volatility_penalty"],
            report["reward_adjustment"]["after"]["volatility_penalty"],
        )
        self.assertIn("self_healing:trade-loss-1", firestore.snapshots)
        self.assertTrue((artifacts / "post_mortems" / "trade-loss-1.json").exists())

    def test_profitable_trade_does_not_trigger_self_healing(self):
        artifacts = Path.cwd() / "tmp-self-healing-tests-profit"
        settings = Settings(model_dir=str(artifacts), redis_url="redis://unused")
        service = TestableSelfHealingPPOService(settings=settings, cache=InMemoryCache(), firestore=StubFirestore())

        report = service.handle_trade_outcome(
            trade_id="trade-win-1",
            active_trade={"symbol": "BTCUSDT", "notional": 1000.0},
            pnl=25.0,
        )

        self.assertIsNone(report)
        self.assertFalse((artifacts / "post_mortems" / "trade-win-1.json").exists())

    def test_existing_reward_profile_is_loaded_and_adjusted(self):
        artifacts = Path.cwd() / "tmp-self-healing-tests-existing"
        artifacts.mkdir(parents=True, exist_ok=True)
        profile_path = artifacts / "self_healing_reward_profile.json"
        profile_path.write_text(
            json.dumps(
                {
                    "volatility_penalty": 1.4,
                    "low_volume_penalty": 1.2,
                    "confidence_miscalibration_penalty": 0.7,
                    "reward_floor": -2.5,
                }
            ),
            encoding="utf-8",
        )
        settings = Settings(model_dir=str(artifacts), redis_url="redis://unused")
        service = TestableSelfHealingPPOService(settings=settings, cache=InMemoryCache(), firestore=StubFirestore())

        report = service.handle_trade_outcome(
            trade_id="trade-loss-2",
            active_trade={
                "symbol": "ETHUSDT",
                "side": "BUY",
                "status": "FILLED",
                "notional": 800.0,
                "confidence": 0.79,
                "expected_return": 0.009,
                "expected_risk": 0.032,
                "actual_slippage_bps": 54.0,
                "feature_snapshot": {
                    "15m_volume": 180000.0,
                    "1m_return": 0.004,
                    "5m_return": 0.011,
                    "order_book_imbalance": 0.18,
                },
                "regime_confidence": 0.73,
            },
            pnl=-20.0,
        )

        self.assertGreaterEqual(report["reward_adjustment"]["before"]["volatility_penalty"], 1.4)
        self.assertGreater(
            report["reward_adjustment"]["after"]["confidence_miscalibration_penalty"],
            report["reward_adjustment"]["before"]["confidence_miscalibration_penalty"],
        )

    def test_nightly_sniper_threshold_tuning_updates_symbol_thresholds(self):
        artifacts = Path.cwd() / "tmp-self-healing-thresholds"
        settings = Settings(model_dir=str(artifacts), redis_url="redis://unused")
        cache = InMemoryCache()
        service = TestableSelfHealingPPOService(settings=settings, cache=cache, firestore=StubFirestore())

        service.record_sniper_trade_outcome(
            {
                "symbol": "BTCUSDT",
                "strategy": "SNIPER_TREND",
                "feature_snapshot": {"1m_rsi": 58.0, "5m_rsi": 54.0},
            },
            pnl=-10.0,
            report={"feature_importance": {"confidence_miscalibration": 0.4}},
        )
        service.record_sniper_trade_outcome(
            {
                "symbol": "BTCUSDT",
                "strategy": "SNIPER_TREND",
                "feature_snapshot": {"1m_rsi": 60.0, "5m_rsi": 55.0},
            },
            pnl=-8.0,
            report={"feature_importance": {"confidence_miscalibration": 0.5}},
        )

        result = service.nightly_sniper_threshold_tuning()

        self.assertEqual(result["updated_symbols"], 1)
        tuned = cache.get_json("dual_track:thresholds:BTCUSDT")
        self.assertGreaterEqual(tuned["long_entry_rsi"], 59.0)
        self.assertGreaterEqual(tuned["long_confirmation_rsi"], 54.5)


if __name__ == "__main__":
    unittest.main()
