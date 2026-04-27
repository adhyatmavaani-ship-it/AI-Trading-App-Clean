import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.model_registry import ModelRegistry


class ModelRegistryVectorizationTest(unittest.TestCase):
    def test_vectorize_features_coerces_string_market_state(self):
        vector = ModelRegistry.vectorize_features(
            {
                "15m_ema_spread": 0.0125,
                "regime": "TRENDING",
                "factor_regime": "RANGING",
                "strict_trade_allowed": True,
                "nullable_value": None,
            }
        )

        self.assertEqual(vector.dtype, np.float32)
        self.assertEqual(len(vector), 5)
        self.assertIn(np.float32(1.0), vector)
        self.assertIn(np.float32(0.0), vector)


if __name__ == "__main__":
    unittest.main()
