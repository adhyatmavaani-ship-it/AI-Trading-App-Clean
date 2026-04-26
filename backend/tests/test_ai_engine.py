import unittest
import sys
from pathlib import Path

import numpy as np

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.schemas.trading import FeatureSnapshot
from app.services.ai_engine import AIEngine


class StubClassifier:
    class model:
        classes_ = ["BUY", "HOLD", "SELL"]

    def predict_proba(self, x):
        return np.array([[0.65, 0.20, 0.15]], dtype=np.float32)


class StubRegistry:
    def load_scaler(self):
        return None

    def sequence_model_supported(self) -> bool:
        return False

    def load_sequence_model(self, input_size: int):
        raise RuntimeError("sequence model unavailable")

    def load_classifier(self):
        return StubClassifier()

    def current_version(self) -> str:
        return "v1"

    @staticmethod
    def vectorize_features(features: dict[str, float]) -> np.ndarray:
        keys = sorted(features.keys())
        return np.array([features[key] for key in keys], dtype=np.float32)


class AIEngineTest(unittest.TestCase):
    def test_infer_falls_back_when_sequence_model_unavailable(self):
        engine = AIEngine(StubRegistry())
        snapshot = FeatureSnapshot(
            symbol="BTCUSDT",
            price=100000,
            timestamp="2026-01-01T00:00:00Z",
            regime="TRENDING",
            regime_confidence=0.8,
            volatility=0.02,
            atr=900,
            order_book_imbalance=0.12,
            features={"15m_ema_spread": 0.004, "15m_volume": 1500000.0},
        )

        inference = engine.infer(snapshot)

        self.assertIn(inference.decision, {"BUY", "SELL", "HOLD"})
        self.assertGreaterEqual(inference.trade_probability, 0.0)
        self.assertLessEqual(inference.trade_probability, 1.0)
        self.assertEqual(inference.model_version, "v1")


if __name__ == "__main__":
    unittest.main()
