import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.trade_probability import TradeProbabilityEngine


class StubRegistry:
    def load_probability_model(self):
        return None

    def load_probability_scaler(self):
        return None

    def load_probability_metadata(self):
        return {}


class TradeProbabilityWeightingTest(unittest.TestCase):
    def test_high_conviction_losses_get_extra_weight(self):
        settings = Settings(
            redis_url="redis://unused",
            retrain_high_confidence_threshold=0.75,
            retrain_high_confidence_loss_weight=2.5,
        )
        engine = TradeProbabilityEngine(settings=settings, registry=StubRegistry())

        row = engine._training_row(
            {
                "outcome": 0.0,
                "confidence": 0.95,
                "features": {"15m_rsi": 55.0, "15m_adx": 25.0, "15m_atr": 1.0, "price": 100.0},
                "closed_at": "2026-04-05T00:00:00+00:00",
            }
        )

        self.assertIsNotNone(row)
        self.assertGreater(row["sample_weight"], 1.0)


if __name__ == "__main__":
    unittest.main()
