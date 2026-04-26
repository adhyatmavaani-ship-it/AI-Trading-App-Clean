import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.schemas.trading import AIInference, FeatureSnapshot
from app.services.risk_engine import RiskEngine


class RiskEngineAdvancedTest(unittest.TestCase):
    def test_correlation_and_alpha_risk_reduce_budget(self):
        settings = Settings(correlation_penalty_threshold=0.75)
        engine = RiskEngine(settings)
        snapshot = FeatureSnapshot(
            symbol="BTCUSDT",
            price=100_000,
            timestamp="2026-01-01T00:00:00Z",
            regime="TRENDING",
            regime_confidence=0.8,
            volatility=0.02,
            atr=500,
            order_book_imbalance=0.2,
            features={},
        )
        inference = AIInference(
            price_forecast_return=0.01,
            expected_return=0.008,
            expected_risk=0.02,
            trade_probability=0.75,
            confidence_score=0.75,
            decision="BUY",
            model_version="v1",
            model_breakdown={},
            reason="test",
        )
        base = engine.evaluate(20_000, snapshot, inference, daily_pnl_pct=0, consecutive_losses=0)
        penalized = engine.evaluate(
            20_000,
            snapshot,
            inference,
            daily_pnl_pct=0,
            consecutive_losses=0,
            correlation_to_portfolio=0.90,
            alpha_risk_score=0.50,
            hours_since_rebalance=24,
        )
        self.assertLess(penalized.risk_budget, base.risk_budget)
        self.assertTrue(penalized.rebalance_required)


if __name__ == "__main__":
    unittest.main()
