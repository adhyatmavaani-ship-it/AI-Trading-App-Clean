import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.schemas.trading import AlphaContext, AIInference, FeatureSnapshot
from app.services.alpha_engine import AlphaEngine


class AlphaEngineTest(unittest.TestCase):
    def test_alpha_engine_allows_high_quality_trade(self):
        engine = AlphaEngine()
        snapshot = FeatureSnapshot(
            symbol="BTCUSDT",
            price=100000,
            timestamp="2026-01-01T00:00:00Z",
            regime="TRENDING",
            regime_confidence=0.8,
            volatility=0.015,
            atr=400,
            order_book_imbalance=0.2,
            features={},
        )
        inference = AIInference(
            price_forecast_return=0.012,
            expected_return=0.01,
            expected_risk=0.01,
            trade_probability=0.78,
            confidence_score=0.78,
            decision="BUY",
            model_version="v1",
            model_breakdown={},
            reason="alpha test",
        )
        alpha = AlphaContext()
        alpha.whale.score = 0.8
        alpha.whale.accumulation_score = 0.85
        alpha.sentiment.hype_score = 0.9
        alpha.sentiment.buzz_score = 0.7
        alpha.liquidity.rug_pull_risk = 0.1
        alpha.security.honeypot_risk = 0.1
        alpha.security.blacklist_risk = 0.1

        result = engine.score(snapshot, inference, alpha, {"source_metrics": {"ai": {"win_rate": 0.58, "profit_factor": 1.3}}})

        self.assertGreater(result["final_score"], 60)
        self.assertTrue(result["allow_trade"])


if __name__ == "__main__":
    unittest.main()
