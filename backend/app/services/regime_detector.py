from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings


@dataclass
class RegimeDetector:
    settings: Settings | None = None

    def __post_init__(self) -> None:
        self.settings = self.settings or Settings()

    def detect_regime(self, data: dict[str, float]) -> tuple[str, float]:
        atr = float(data.get("atr", 0.0) or 0.0)
        avg_atr = float(data.get("avg_atr", atr) or atr)
        ema_fast = float(data.get("ema_fast", 0.0) or 0.0)
        ema_slow = float(data.get("ema_slow", 0.0) or 0.0)
        price = float(data.get("price", max(ema_fast, ema_slow, 1.0)) or 1.0)
        trend_strength = abs(ema_fast - ema_slow) / max(price, 1e-8)

        if atr > avg_atr * float(self.settings.regime_high_vol_atr_multiplier):
            confidence = min(1.0, atr / max(avg_atr * float(self.settings.regime_high_vol_atr_multiplier), 1e-8))
            return "HIGH_VOL", max(0.55, confidence)

        if trend_strength > float(self.settings.regime_trending_ema_spread_threshold):
            confidence = min(1.0, trend_strength / max(float(self.settings.regime_trending_ema_spread_threshold), 1e-8))
            return "TRENDING", max(0.55, confidence)

        if atr < avg_atr * float(self.settings.regime_low_vol_atr_multiplier):
            confidence = min(1.0, (avg_atr * float(self.settings.regime_low_vol_atr_multiplier)) / max(atr, 1e-8))
            return "LOW_VOL", max(0.5, min(confidence, 0.95))

        return "RANGING", 0.6

    def classify(self, trend_strength: float, volatility: float, mean_reversion: float) -> tuple[str, float]:
        synthetic = {
            "atr": float(volatility),
            "avg_atr": max(float(volatility), 1e-6),
            "ema_fast": float(trend_strength + 1.0),
            "ema_slow": 1.0,
            "price": 1.0,
        }
        regime, confidence = self.detect_regime(synthetic)
        if regime == "LOW_VOL" and float(mean_reversion) > 0.25:
            return "RANGING", max(confidence, 0.55)
        return regime, confidence
