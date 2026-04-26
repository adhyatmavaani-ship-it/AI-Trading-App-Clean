import unittest
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.schemas.monitoring import DrawdownStatus, ModelStabilityStatus, RolloutStatus
from app.services.drawdown_protection import DrawdownProtectionService
from app.services.meta_controller import MetaController
from app.services.redis_state_manager import RedisStateManager
from app.services.risk_engine import RiskEngine
from app.services.system_monitor import SystemMonitorService


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


class StubRolloutManager:
    def status(self):
        return RolloutStatus(
            stage_index=1,
            stage_name="MICRO",
            capital_fraction=0.25,
            mode="paper",
            eligible_for_upgrade=False,
            downgrade_flag=False,
        )


class StubModelStability:
    def load_status(self):
        return ModelStabilityStatus(
            active_model_version="v1",
            fallback_model_version=None,
            live_win_rate=0.58,
            training_win_rate=0.60,
            drift_score=0.02,
            calibration_error=0.01,
            feature_drift_score=0.0,
            concept_drift_score=0.02,
            retraining_triggered=False,
            trading_frequency_multiplier=1.0,
            degraded=False,
        )


class StubPortfolioLedger:
    def __init__(self, profile: dict | None = None):
        self.profile = profile or {}

    def latest_concentration_profile(self, user_id: str) -> dict:
        return dict(self.profile)


class MetaControllerTest(unittest.TestCase):
    def setUp(self):
        self.cache = InMemoryCache()
        self.settings = Settings(redis_url="redis://unused")
        self.drawdown = DrawdownProtectionService(self.settings, self.cache)
        self.monitor = SystemMonitorService(self.settings, self.cache)
        self.redis_state = RedisStateManager(self.settings, self.cache)
        self.controller = MetaController(
            settings=self.settings,
            cache=self.cache,
            system_monitor=self.monitor,
            drawdown_protection=self.drawdown,
            risk_engine=RiskEngine(self.settings),
            rollout_manager=StubRolloutManager(),
            model_stability=StubModelStability(),
            redis_state_manager=self.redis_state,
            portfolio_ledger=StubPortfolioLedger(),
        )

    def test_health_check_blocks_when_api_success_rate_is_low(self):
        self.cache.set("monitor:execution_latency_ms", "40", ttl=60)
        self.monitor.record_api_call(success=True)
        self.monitor.record_api_call(success=False)

        decision = self.controller.govern_signal(
            user_id="u1",
            symbol="BTCUSDT",
            side="BUY",
            proposed_strategy="AI",
            volatility=0.01,
            macro_bias={"regime": "NEUTRAL", "multiplier": 1.0},
            liquidity_stability=0.9,
            latency_ms=40.0,
            ai_score=82.0,
            ai_confidence=0.81,
            whale_score=0.72,
            sentiment_score=0.75,
        )

        self.assertFalse(decision.allow_trade)
        self.assertIn("API success rate fell below threshold", decision.reasons)

    def test_confidence_gate_blocks_bullish_trade_against_bearish_macro(self):
        decision = self.controller.govern_signal(
            user_id="u1",
            symbol="BTCUSDT",
            side="BUY",
            proposed_strategy="AI",
            volatility=0.01,
            macro_bias={"regime": "BEARISH", "multiplier": 0.5},
            liquidity_stability=0.9,
            latency_ms=40.0,
            ai_score=90.0,
            ai_confidence=0.80,
            whale_score=0.20,
            sentiment_score=0.90,
        )

        self.assertFalse(decision.allow_trade)
        self.assertIn("Macro bias is bearish against a long setup", decision.reasons)

    def test_capital_allocation_increases_after_winning_streak(self):
        active_trade = {"symbol": "BTCUSDT", "notional": 100.0}
        self.controller.record_trade_outcome(user_id="u1", active_trade=active_trade, pnl=10.0)
        self.controller.record_trade_outcome(user_id="u1", active_trade=active_trade, pnl=12.0)

        allocation = self.controller.capital_allocation(
            user_id="u1",
            strategy="AI",
            volatility=0.01,
            macro_bias={"regime": "NEUTRAL", "multiplier": 1.0},
            regime_type="TRENDING",
            trade_intelligence_metrics={"win_rate": 0.61, "avg_r_multiple": 0.85, "avg_drawdown": 0.02},
        )

        self.assertGreater(allocation["capital_multiplier"], 1.0)
        self.assertEqual(allocation["action"], "allocate_capital")

    def test_capital_allocation_is_reduced_when_model_inputs_are_unstable(self):
        class ReducedFrequencyStability(StubModelStability):
            def load_status(self_inner):
                payload = super().load_status()
                return payload.model_copy(update={"trading_frequency_multiplier": 0.5})

        self.controller.model_stability = ReducedFrequencyStability()

        allocation = self.controller.capital_allocation(
            user_id="u1",
            strategy="AI",
            volatility=0.01,
            macro_bias={"regime": "NEUTRAL", "multiplier": 1.0},
            regime_type="TRENDING",
            trade_intelligence_metrics={"win_rate": 0.60, "avg_r_multiple": 0.70, "avg_drawdown": 0.02},
        )

        self.assertLess(allocation["capital_multiplier"], 1.0)

    def test_logs_meta_decision_and_updates_analytics(self):
        decision = self.controller.govern_signal(
            user_id="u1",
            symbol="BTCUSDT",
            side="SELL",
            proposed_strategy="AI",
            volatility=0.01,
            macro_bias={"regime": "BEARISH", "multiplier": 0.5},
            liquidity_stability=0.9,
            latency_ms=40.0,
            ai_score=78.0,
            ai_confidence=0.73,
            whale_score=0.62,
            sentiment_score=0.55,
            regime_type="TRENDING",
            trade_intelligence_metrics={"win_rate": 0.60, "avg_r_multiple": 0.60, "avg_drawdown": 0.02},
        )

        payload = self.controller.log_decision(
            trade_id="trade-123",
            user_id="u1",
            symbol="BTCUSDT",
            decision=decision,
            signals={"ai_score": 78.0, "confidence": decision.confidence_score},
            conflicts=decision.reasons,
            risk_adjustments={"meta_capital_multiplier": decision.capital_multiplier},
            reason="Approved by meta control",
        )

        self.assertEqual(payload["decision"], "APPROVED")
        self.assertEqual(self.controller.get_decision_log("trade-123")["strategy"], decision.selected_strategy)
        analytics = self.controller.analytics_snapshot()
        self.assertIn(decision.selected_strategy, analytics["strategy_performance"])
        self.assertTrue(analytics["confidence_distribution"])

    def test_meta_controller_reduces_size_for_mediocre_regime_quality(self):
        decision = self.controller.govern_signal(
            user_id="u1",
            symbol="BTCUSDT",
            side="SELL",
            proposed_strategy="AI",
            volatility=0.01,
            macro_bias={"regime": "NEUTRAL", "multiplier": 1.0},
            liquidity_stability=0.9,
            latency_ms=40.0,
            ai_score=80.0,
            ai_confidence=0.76,
            whale_score=0.68,
            sentiment_score=0.58,
            regime_type="RANGING",
            trade_intelligence_metrics={"win_rate": 0.51, "avg_r_multiple": 0.22, "avg_drawdown": 0.03},
        )

        self.assertTrue(decision.allow_trade)
        self.assertEqual(decision.allocation_action, "reduce_size")
        self.assertLess(decision.capital_multiplier, 1.0)

    def test_meta_controller_skips_trade_for_weak_regime_quality(self):
        decision = self.controller.govern_signal(
            user_id="u1",
            symbol="BTCUSDT",
            side="BUY",
            proposed_strategy="AI",
            volatility=0.01,
            macro_bias={"regime": "NEUTRAL", "multiplier": 1.0},
            liquidity_stability=0.9,
            latency_ms=40.0,
            ai_score=84.0,
            ai_confidence=0.80,
            whale_score=0.72,
            sentiment_score=0.62,
            regime_type="RANGING",
            trade_intelligence_metrics={"win_rate": 0.45, "avg_r_multiple": -0.05, "avg_drawdown": 0.03},
        )

        self.assertFalse(decision.allow_trade)
        self.assertEqual(decision.allocation_action, "skip_trade")
        self.assertEqual(decision.capital_multiplier, 0.0)

    def test_meta_controller_reduces_size_when_portfolio_concentration_pressure_is_high(self):
        self.controller.portfolio_ledger = StubPortfolioLedger(
            {
                "gross_exposure_pct": 0.58,
                "candidate_theme_exposure_pct": 0.25,
                "cluster_exposure_pct": {"CLUSTER_1": 0.36},
                "beta_bucket_exposure_pct": {"BETA_HIGH": 0.32},
                "gross_exposure_drift": 0.06,
                "cluster_concentration_drift": 0.05,
                "beta_bucket_concentration_drift": 0.04,
                "cluster_turnover": 0.45,
            }
        )

        decision = self.controller.govern_signal(
            user_id="u1",
            symbol="BTCUSDT",
            side="BUY",
            proposed_strategy="AI",
            volatility=0.01,
            macro_bias={"regime": "NEUTRAL", "multiplier": 1.0},
            liquidity_stability=0.9,
            latency_ms=40.0,
            ai_score=84.0,
            ai_confidence=0.80,
            whale_score=0.72,
            sentiment_score=0.62,
            regime_type="TRENDING",
            trade_intelligence_metrics={"win_rate": 0.60, "avg_r_multiple": 0.80, "avg_drawdown": 0.02},
        )

        self.assertTrue(decision.allow_trade)
        self.assertEqual(decision.allocation_action, "reduce_size")
        self.assertLess(decision.capital_multiplier, 1.0)
        self.assertTrue(any("concentration" in reason.lower() for reason in decision.reasons))

    def test_meta_controller_softens_capital_on_rising_concentration_drift(self):
        self.controller.portfolio_ledger = StubPortfolioLedger(
            {
                "gross_exposure_pct": 0.40,
                "candidate_theme_exposure_pct": 0.12,
                "cluster_exposure_pct": {"CLUSTER_1": 0.20},
                "beta_bucket_exposure_pct": {"BETA_MID": 0.18},
                "gross_exposure_drift": 0.035,
                "cluster_concentration_drift": 0.02,
                "beta_bucket_concentration_drift": 0.01,
                "cluster_turnover": 0.18,
            }
        )

        decision = self.controller.govern_signal(
            user_id="u1",
            symbol="ETHUSDT",
            side="BUY",
            proposed_strategy="AI",
            volatility=0.01,
            macro_bias={"regime": "NEUTRAL", "multiplier": 1.0},
            liquidity_stability=0.9,
            latency_ms=40.0,
            ai_score=82.0,
            ai_confidence=0.78,
            whale_score=0.70,
            sentiment_score=0.60,
            regime_type="TRENDING",
            trade_intelligence_metrics={"win_rate": 0.60, "avg_r_multiple": 0.80, "avg_drawdown": 0.02},
        )

        self.assertTrue(decision.allow_trade)
        self.assertEqual(decision.allocation_action, "reduce_size")
        self.assertLess(decision.capital_multiplier, 1.0)
        self.assertTrue(any("drift" in reason.lower() for reason in decision.reasons))

    def test_meta_controller_softens_capital_when_factor_sleeve_is_crowded(self):
        self.controller.portfolio_ledger = StubPortfolioLedger(
            {
                "gross_exposure_pct": 0.34,
                "candidate_theme_exposure_pct": 0.12,
                "cluster_exposure_pct": {"CLUSTER_1": 0.16},
                "beta_bucket_exposure_pct": {"BETA_MID": 0.14},
                "factor_attribution": {"BTCUSDT": 0.42, "ETHUSDT": 0.28},
                "factor_sleeve_performance": {
                    "BTCUSDT": {
                        "recent_realized_pnl": 18.0,
                        "recent_win_rate": 0.67,
                    }
                },
                "dominant_factor_sleeve": "BTCUSDT",
                "gross_exposure_drift": 0.01,
                "cluster_concentration_drift": 0.01,
                "beta_bucket_concentration_drift": 0.01,
                "cluster_turnover": 0.10,
            }
        )

        decision = self.controller.govern_signal(
            user_id="u1",
            symbol="BTCUSDT",
            side="BUY",
            proposed_strategy="AI",
            volatility=0.01,
            macro_bias={"regime": "NEUTRAL", "multiplier": 1.0},
            liquidity_stability=0.9,
            latency_ms=40.0,
            ai_score=82.0,
            ai_confidence=0.78,
            whale_score=0.70,
            sentiment_score=0.60,
            regime_type="TRENDING",
            trade_intelligence_metrics={"win_rate": 0.60, "avg_r_multiple": 0.80, "avg_drawdown": 0.02},
        )

        self.assertTrue(decision.allow_trade)
        self.assertEqual(decision.allocation_action, "allocate_capital")
        self.assertGreaterEqual(decision.capital_multiplier, 1.0)
        self.assertTrue(any("rotating capital selectively" in reason.lower() for reason in decision.reasons))
        self.assertTrue(any("stronger recent sleeves" in reason.lower() for reason in decision.reasons))

    def test_meta_controller_penalizes_deteriorating_crowded_factor_sleeve_more(self):
        self.controller.portfolio_ledger = StubPortfolioLedger(
            {
                "gross_exposure_pct": 0.34,
                "candidate_theme_exposure_pct": 0.12,
                "cluster_exposure_pct": {"CLUSTER_1": 0.16},
                "beta_bucket_exposure_pct": {"BETA_MID": 0.14},
                "factor_attribution": {"BTCUSDT": 0.42, "ETHUSDT": 0.28},
                "factor_sleeve_performance": {
                    "BTCUSDT": {
                        "recent_realized_pnl": -9.0,
                        "recent_win_rate": 0.33,
                    }
                },
                "dominant_factor_sleeve": "BTCUSDT",
                "gross_exposure_drift": 0.01,
                "cluster_concentration_drift": 0.01,
                "beta_bucket_concentration_drift": 0.01,
                "cluster_turnover": 0.10,
            }
        )

        decision = self.controller.govern_signal(
            user_id="u1",
            symbol="BTCUSDT",
            side="BUY",
            proposed_strategy="AI",
            volatility=0.01,
            macro_bias={"regime": "NEUTRAL", "multiplier": 1.0},
            liquidity_stability=0.9,
            latency_ms=40.0,
            ai_score=82.0,
            ai_confidence=0.78,
            whale_score=0.70,
            sentiment_score=0.60,
            regime_type="TRENDING",
            trade_intelligence_metrics={"win_rate": 0.60, "avg_r_multiple": 0.80, "avg_drawdown": 0.02},
        )

        self.assertTrue(decision.allow_trade)
        self.assertEqual(decision.allocation_action, "reduce_size")
        self.assertTrue(any("losing recent quality" in reason.lower() for reason in decision.reasons))

    def test_meta_controller_skips_trade_for_crowded_and_failing_factor_sleeve(self):
        self.controller.portfolio_ledger = StubPortfolioLedger(
            {
                "factor_attribution": {"BTCUSDT": 0.44, "ETHUSDT": 0.20},
                "factor_sleeve_performance": {
                    "BTCUSDT": {
                        "recent_realized_pnl": -0.20,
                        "recent_win_rate": 0.20,
                        "recent_avg_pnl": -0.04,
                        "recent_closed_trades": 6,
                    }
                },
                "dominant_factor_sleeve": "BTCUSDT",
            }
        )

        decision = self.controller.govern_signal(
            user_id="u1",
            symbol="BTCUSDT",
            side="BUY",
            proposed_strategy="AI",
            volatility=0.01,
            macro_bias={"regime": "NEUTRAL", "multiplier": 1.0},
            liquidity_stability=0.9,
            latency_ms=40.0,
            ai_score=82.0,
            ai_confidence=0.78,
            whale_score=0.70,
            sentiment_score=0.60,
            regime_type="TRENDING",
            trade_intelligence_metrics={"win_rate": 0.60, "avg_r_multiple": 0.80, "avg_drawdown": 0.02},
        )

        self.assertFalse(decision.allow_trade)
        self.assertEqual(decision.allocation_action, "skip_trade")
        self.assertTrue(any("rotating capital away" in reason.lower() for reason in decision.reasons))

    def test_meta_controller_keeps_more_budget_for_strong_recent_sleeve(self):
        self.controller.portfolio_ledger = StubPortfolioLedger(
            {
                "factor_attribution": {"BTCUSDT": 0.38, "ETHUSDT": 0.24},
                "factor_sleeve_budget_targets": {"BTCUSDT": 0.46, "ETHUSDT": 0.18},
                "factor_sleeve_budget_deltas": {"BTCUSDT": 0.08, "ETHUSDT": -0.06},
                "factor_sleeve_budget_turnover": 0.08,
                "max_factor_sleeve_budget_gap_pct": 0.03,
                "factor_sleeve_performance": {
                    "BTCUSDT": {
                        "recent_realized_pnl": 0.30,
                        "recent_win_rate": 0.70,
                        "recent_avg_pnl": 0.025,
                        "recent_closed_trades": 8,
                    }
                },
                "dominant_factor_sleeve": "BTCUSDT",
            }
        )

        decision = self.controller.govern_signal(
            user_id="u1",
            symbol="BTCUSDT",
            side="BUY",
            proposed_strategy="AI",
            volatility=0.01,
            macro_bias={"regime": "NEUTRAL", "multiplier": 1.0},
            liquidity_stability=0.9,
            latency_ms=40.0,
            ai_score=82.0,
            ai_confidence=0.78,
            whale_score=0.70,
            sentiment_score=0.60,
            regime_type="TRENDING",
            trade_intelligence_metrics={"win_rate": 0.60, "avg_r_multiple": 0.80, "avg_drawdown": 0.02},
        )

        self.assertTrue(decision.allow_trade)
        self.assertEqual(decision.allocation_action, "allocate_capital")
        self.assertGreaterEqual(decision.capital_multiplier, 1.0)
        self.assertTrue(any("stronger recent sleeves" in reason.lower() for reason in decision.reasons))

    def test_meta_controller_suppresses_sleeve_priority_boost_when_rotation_is_unstable(self):
        self.controller.portfolio_ledger = StubPortfolioLedger(
            {
                "factor_attribution": {"BTCUSDT": 0.38, "ETHUSDT": 0.24},
                "factor_sleeve_budget_targets": {"BTCUSDT": 0.46, "ETHUSDT": 0.18},
                "factor_sleeve_budget_deltas": {"BTCUSDT": 0.08, "ETHUSDT": -0.06},
                "factor_sleeve_budget_turnover": self.settings.portfolio_concentration_soft_turnover + 0.02,
                "max_factor_sleeve_budget_gap_pct": 0.03,
                "factor_sleeve_performance": {
                    "BTCUSDT": {
                        "recent_realized_pnl": 0.30,
                        "recent_win_rate": 0.70,
                        "recent_avg_pnl": 0.025,
                        "recent_closed_trades": 8,
                    }
                },
                "dominant_factor_sleeve": "BTCUSDT",
            }
        )

        decision = self.controller.govern_signal(
            user_id="u1",
            symbol="BTCUSDT",
            side="BUY",
            proposed_strategy="AI",
            volatility=0.01,
            macro_bias={"regime": "NEUTRAL", "multiplier": 1.0},
            liquidity_stability=0.9,
            latency_ms=40.0,
            ai_score=82.0,
            ai_confidence=0.78,
            whale_score=0.70,
            sentiment_score=0.60,
            regime_type="TRENDING",
            trade_intelligence_metrics={"win_rate": 0.60, "avg_r_multiple": 0.80, "avg_drawdown": 0.02},
        )

        self.assertTrue(decision.allow_trade)
        self.assertTrue(any("priority boost suppressed" in reason.lower() for reason in decision.reasons))

    def test_meta_controller_reduces_confidence_for_weak_overweight_sleeve(self):
        self.controller.portfolio_ledger = StubPortfolioLedger(
            {
                "factor_attribution": {"BTCUSDT": 0.41, "ETHUSDT": 0.19},
                "factor_sleeve_budget_targets": {"BTCUSDT": 0.26, "ETHUSDT": 0.34},
                "factor_sleeve_budget_deltas": {"BTCUSDT": -0.15, "ETHUSDT": 0.15},
                "factor_sleeve_performance": {
                    "BTCUSDT": {
                        "recent_realized_pnl": -0.12,
                        "recent_win_rate": 0.30,
                        "recent_avg_pnl": -0.02,
                        "recent_closed_trades": 8,
                    }
                },
                "dominant_factor_sleeve": "BTCUSDT",
            }
        )

        decision = self.controller.govern_signal(
            user_id="u1",
            symbol="BTCUSDT",
            side="BUY",
            proposed_strategy="AI",
            volatility=0.01,
            macro_bias={"regime": "NEUTRAL", "multiplier": 1.0},
            liquidity_stability=0.9,
            latency_ms=40.0,
            ai_score=72.0,
            ai_confidence=0.70,
            whale_score=0.62,
            sentiment_score=0.58,
            regime_type="TRENDING",
            trade_intelligence_metrics={"win_rate": 0.60, "avg_r_multiple": 0.80, "avg_drawdown": 0.02},
        )

        self.assertFalse(decision.allow_trade)
        self.assertTrue(any("budget quality expectations" in reason.lower() for reason in decision.reasons))


if __name__ == "__main__":
    unittest.main()
