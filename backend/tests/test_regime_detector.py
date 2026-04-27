import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.regime_detector import RegimeDetector


class RegimeDetectorTest(unittest.TestCase):
    def setUp(self):
        self.detector = RegimeDetector(Settings(redis_url="redis://unused"))

    def test_detects_high_vol_regime(self):
        regime, confidence = self.detector.detect_regime(
            {"atr": 3.2, "avg_atr": 2.0, "ema_fast": 101.0, "ema_slow": 100.0, "price": 100.0}
        )
        self.assertEqual(regime, "HIGH_VOL")
        self.assertGreaterEqual(confidence, 0.55)

    def test_detects_trending_regime(self):
        regime, _ = self.detector.detect_regime(
            {"atr": 1.0, "avg_atr": 1.0, "ema_fast": 101.0, "ema_slow": 100.0, "price": 100.0}
        )
        self.assertEqual(regime, "TRENDING")

    def test_detects_low_vol_regime(self):
        regime, _ = self.detector.detect_regime(
            {"atr": 0.5, "avg_atr": 1.0, "ema_fast": 100.1, "ema_slow": 100.0, "price": 100.0}
        )
        self.assertEqual(regime, "LOW_VOL")

    def test_detects_ranging_regime(self):
        regime, _ = self.detector.detect_regime(
            {"atr": 1.0, "avg_atr": 1.0, "ema_fast": 100.1, "ema_slow": 100.0, "price": 100.0}
        )
        self.assertEqual(regime, "RANGING")


if __name__ == "__main__":
    unittest.main()
