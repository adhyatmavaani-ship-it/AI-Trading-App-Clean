import unittest
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.schemas.trading import AIInference, FeatureSnapshot
from app.services.risk_engine import RiskEngine


class RiskEngineTest(unittest.TestCase):
    def test_risk_engine_reduces_risk_during_high_volatility(self):
        engine = RiskEngine(Settings())
        snapshot = FeatureSnapshot(
            symbol="BTCUSDT",
            price=100_000,
            timestamp="2026-01-01T00:00:00Z",
            regime="VOLATILE",
            regime_confidence=0.8,
            volatility=0.05,
            atr=1200,
            order_book_imbalance=0.1,
            features={},
        )
        inference = AIInference(
            price_forecast_return=0.01,
            expected_return=0.012,
            expected_risk=0.03,
            trade_probability=0.7,
            confidence_score=0.7,
            decision="BUY",
            model_version="v1",
            model_breakdown={},
            reason="test",
        )
        decision = engine.evaluate(10_000, snapshot, inference, daily_pnl_pct=0, consecutive_losses=0)
        self.assertLess(decision.risk_budget, 250)
        self.assertGreater(decision.atr_stop_distance, 0)

    def test_global_limits_raise_when_trade_frequency_is_too_high(self):
        engine = RiskEngine(Settings())

        with self.assertRaisesRegex(ValueError, "trades-per-hour"):
            engine.check_global_limits(
                drawdown_pct=0.01,
                trades_this_hour=engine.settings.meta_max_trades_per_hour,
                asset_exposure_pct=0.05,
            )

    def test_abnormal_loss_limit_triggers_kill_switch_before_daily_limit(self):
        settings = Settings(daily_loss_limit=0.05, abnormal_loss_limit=0.08)
        engine = RiskEngine(settings)
        snapshot = FeatureSnapshot(
            symbol="BTCUSDT",
            price=100_000,
            timestamp="2026-01-01T00:00:00Z",
            regime="VOLATILE",
            regime_confidence=0.8,
            volatility=0.05,
            atr=1200,
            order_book_imbalance=0.1,
            features={},
        )
        inference = AIInference(
            price_forecast_return=0.01,
            expected_return=0.012,
            expected_risk=0.03,
            trade_probability=0.7,
            confidence_score=0.7,
            decision="BUY",
            model_version="v1",
            model_breakdown={},
            reason="test",
        )

        with self.assertRaisesRegex(ValueError, "Kill switch engaged"):
            engine.evaluate(10_000, snapshot, inference, daily_pnl_pct=-0.09, consecutive_losses=0)

    def test_notional_exposure_input_is_normalized_before_projection(self):
        engine = RiskEngine(Settings())
        snapshot = FeatureSnapshot(
            symbol="BTCUSDT",
            price=100_000,
            timestamp="2026-01-01T00:00:00Z",
            regime="TRENDING",
            regime_confidence=0.8,
            volatility=0.01,
            atr=120_000,
            order_book_imbalance=0.1,
            features={},
        )
        inference = AIInference(
            price_forecast_return=0.01,
            expected_return=0.012,
            expected_risk=0.03,
            trade_probability=0.7,
            confidence_score=0.8,
            decision="BUY",
            model_version="v1",
            model_breakdown={},
            reason="test",
        )

        decision = engine.evaluate(
            10_000,
            snapshot,
            inference,
            daily_pnl_pct=0,
            consecutive_losses=0,
            current_coin_exposure=500.0,
        )

        self.assertLess(decision.exposure_pct, 0.3)

    def test_trade_probability_reduces_position_sizing(self):
        engine = RiskEngine(
            Settings(
                probability_position_floor=0.35,
                probability_position_ceiling=1.15,
                max_coin_exposure_pct=1.0,
            )
        )
        snapshot = FeatureSnapshot(
            symbol="BTCUSDT",
            price=100_000,
            timestamp="2026-01-01T00:00:00Z",
            regime="TRENDING",
            regime_confidence=0.8,
            volatility=0.01,
            atr=120_000,
            order_book_imbalance=0.1,
            features={},
        )
        strong = AIInference(
            price_forecast_return=0.01,
            expected_return=0.012,
            expected_risk=0.03,
            trade_probability=0.9,
            confidence_score=0.8,
            decision="BUY",
            model_version="v1",
            model_breakdown={},
            reason="test",
        )
        weak = strong.model_copy(update={"trade_probability": 0.4})

        strong_decision = engine.evaluate(10_000, snapshot, strong, daily_pnl_pct=0, consecutive_losses=0)
        weak_decision = engine.evaluate(10_000, snapshot, weak, daily_pnl_pct=0, consecutive_losses=0)

        self.assertLess(weak_decision.position_notional, strong_decision.position_notional)

    def test_high_probability_increases_position_size_smoothly(self):
        engine = RiskEngine(
            Settings(
                probability_position_floor=0.35,
                probability_position_ceiling=1.20,
                probability_position_smoothing=1.4,
                max_coin_exposure_pct=1.0,
            )
        )
        snapshot = FeatureSnapshot(
            symbol="BTCUSDT",
            price=100_000,
            timestamp="2026-01-01T00:00:00Z",
            regime="TRENDING",
            regime_confidence=0.8,
            volatility=0.012,
            atr=120_000,
            order_book_imbalance=0.1,
            features={},
        )
        low = AIInference(
            price_forecast_return=0.01,
            expected_return=0.012,
            expected_risk=0.03,
            trade_probability=0.58,
            confidence_score=0.8,
            decision="BUY",
            model_version="v1",
            model_breakdown={},
            reason="test",
        )
        mid = low.model_copy(update={"trade_probability": 0.72})
        high = low.model_copy(update={"trade_probability": 0.90})

        low_decision = engine.evaluate(10_000, snapshot, low, daily_pnl_pct=0, consecutive_losses=0)
        mid_decision = engine.evaluate(10_000, snapshot, mid, daily_pnl_pct=0, consecutive_losses=0)
        high_decision = engine.evaluate(10_000, snapshot, high, daily_pnl_pct=0, consecutive_losses=0)

        self.assertLess(low_decision.position_notional, mid_decision.position_notional)
        self.assertLess(mid_decision.position_notional, high_decision.position_notional)
        self.assertLess(low_decision.position_size_pct, high_decision.position_size_pct)

    def test_position_below_minimum_trade_threshold_is_rejected(self):
        engine = RiskEngine(
            Settings(
                exchange_min_notional=25.0,
                probability_position_floor=0.35,
                max_coin_exposure_pct=1.0,
            )
        )
        snapshot = FeatureSnapshot(
            symbol="BTCUSDT",
            price=100_000,
            timestamp="2026-01-01T00:00:00Z",
            regime="RANGING",
            regime_confidence=0.7,
            volatility=0.02,
            atr=300_000,
            order_book_imbalance=0.1,
            features={},
        )
        inference = AIInference(
            price_forecast_return=0.005,
            expected_return=0.006,
            expected_risk=0.03,
            trade_probability=0.56,
            confidence_score=0.58,
            decision="BUY",
            model_version="v1",
            model_breakdown={},
            reason="test",
        )

        with self.assertRaisesRegex(ValueError, "minimum trade threshold"):
            engine.evaluate(1_000, snapshot, inference, daily_pnl_pct=0, consecutive_losses=0)

    def test_trending_regime_boosts_position_size_over_ranging(self):
        engine = RiskEngine(Settings(max_coin_exposure_pct=1.0))
        inference = AIInference(
            price_forecast_return=0.01,
            expected_return=0.012,
            expected_risk=0.02,
            trade_probability=0.82,
            confidence_score=0.84,
            decision="BUY",
            model_version="v1",
            model_breakdown={},
            reason="test",
        )
        trending = FeatureSnapshot(
            symbol="BTCUSDT",
            price=100_000,
            timestamp="2026-01-01T00:00:00Z",
            regime="TRENDING",
            regime_confidence=0.8,
            volatility=0.012,
            atr=7_500,
            order_book_imbalance=0.1,
            features={},
        )
        ranging = trending.model_copy(update={"regime": "RANGING"})
        trade_metrics = {"win_rate": 0.58, "avg_r_multiple": 0.65, "avg_drawdown": 0.02}

        trending_decision = engine.evaluate(
            10_000,
            trending,
            inference,
            daily_pnl_pct=0,
            consecutive_losses=0,
            trade_intelligence_metrics=trade_metrics,
        )
        ranging_decision = engine.evaluate(
            10_000,
            ranging,
            inference,
            daily_pnl_pct=0,
            consecutive_losses=0,
            trade_intelligence_metrics=trade_metrics,
        )

        self.assertGreater(trending_decision.position_notional, ranging_decision.position_notional)
        self.assertGreater(trending_decision.position_size_pct, ranging_decision.position_size_pct)
        self.assertLessEqual(trending_decision.position_size_pct, 1.0)

    def test_high_vol_regime_reduces_position_size(self):
        engine = RiskEngine(Settings(max_coin_exposure_pct=1.0))
        inference = AIInference(
            price_forecast_return=0.01,
            expected_return=0.012,
            expected_risk=0.02,
            trade_probability=0.80,
            confidence_score=0.82,
            decision="BUY",
            model_version="v1",
            model_breakdown={},
            reason="test",
        )
        trending = FeatureSnapshot(
            symbol="BTCUSDT",
            price=100_000,
            timestamp="2026-01-01T00:00:00Z",
            regime="TRENDING",
            regime_confidence=0.8,
            volatility=0.012,
            atr=7_500,
            order_book_imbalance=0.1,
            features={},
        )
        high_vol = trending.model_copy(update={"regime": "HIGH_VOL", "volatility": 0.04, "atr": 7_500})
        trade_metrics = {"win_rate": 0.56, "avg_r_multiple": 0.50, "avg_drawdown": 0.025}

        trending_decision = engine.evaluate(
            10_000,
            trending,
            inference,
            daily_pnl_pct=0,
            consecutive_losses=0,
            trade_intelligence_metrics=trade_metrics,
        )
        high_vol_decision = engine.evaluate(
            10_000,
            high_vol,
            inference,
            daily_pnl_pct=0,
            consecutive_losses=0,
            trade_intelligence_metrics=trade_metrics,
        )

        self.assertLess(high_vol_decision.position_notional, trending_decision.position_notional)
        self.assertLess(high_vol_decision.position_size_pct, trending_decision.position_size_pct)

    def test_high_vol_regime_can_be_skipped_when_quality_is_poor(self):
        engine = RiskEngine(Settings(max_coin_exposure_pct=1.0, regime_high_vol_skip_volatility=0.05))
        snapshot = FeatureSnapshot(
            symbol="BTCUSDT",
            price=100_000,
            timestamp="2026-01-01T00:00:00Z",
            regime="HIGH_VOL",
            regime_confidence=0.9,
            volatility=0.07,
            atr=2400,
            order_book_imbalance=0.1,
            features={},
        )
        inference = AIInference(
            price_forecast_return=0.01,
            expected_return=0.012,
            expected_risk=0.04,
            trade_probability=0.58,
            confidence_score=0.60,
            decision="BUY",
            model_version="v1",
            model_breakdown={},
            reason="test",
        )

        with self.assertRaisesRegex(ValueError, "High-volatility regime rejected"):
            engine.evaluate(
                10_000,
                snapshot,
                inference,
                daily_pnl_pct=0,
                consecutive_losses=0,
                trade_intelligence_metrics={"win_rate": 0.46, "avg_r_multiple": -0.1, "avg_drawdown": 0.05},
            )

    def test_user_capital_allocation_caps_requested_notional(self):
        engine = RiskEngine(Settings(max_coin_exposure_pct=0.20))

        capped = engine.enforce_user_controls(
            balance=10_000,
            requested_notional=5_000,
            daily_pnl_pct=0.0,
            max_capital_allocation_pct=0.10,
        )

        self.assertEqual(capped, 1_000)

    def test_emergency_stop_blocks_user_trade(self):
        engine = RiskEngine(Settings())

        with self.assertRaisesRegex(ValueError, "Emergency stop"):
            engine.enforce_user_controls(
                balance=10_000,
                requested_notional=500,
                daily_pnl_pct=0.0,
                emergency_stop_active=True,
            )

    def test_user_daily_loss_override_blocks_trade(self):
        engine = RiskEngine(Settings(daily_loss_limit=0.05))

        with self.assertRaisesRegex(ValueError, "Daily loss limit reached"):
            engine.enforce_user_controls(
                balance=10_000,
                requested_notional=500,
                daily_pnl_pct=-0.03,
                daily_loss_limit_override=0.02,
            )


if __name__ == "__main__":
    unittest.main()
