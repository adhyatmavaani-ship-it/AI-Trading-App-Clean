import unittest
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.schemas.trading import AIInference, FeatureSnapshot
from app.services.strategy_engine import StrategyEngine


class StrategyEngineTest(unittest.TestCase):
    def test_strategy_selection_trending_market(self):
        engine = StrategyEngine()
        snapshot = FeatureSnapshot(
            symbol="ETHUSDT",
            price=2500,
            timestamp="2026-01-01T00:00:00Z",
            regime="TRENDING",
            regime_confidence=0.75,
            volatility=0.02,
            atr=40,
            order_book_imbalance=0.05,
            features={},
        )
        inference = AIInference(
            price_forecast_return=0.012,
            expected_return=0.01,
            expected_risk=0.02,
            trade_probability=0.71,
            confidence_score=0.71,
            decision="BUY",
            model_version="v1",
            model_breakdown={},
            reason="trend",
        )
        self.assertEqual(engine.select(snapshot, inference), "TREND_FOLLOW")


if __name__ == "__main__":
    unittest.main()
