from __future__ import annotations

from typing import Any


class PredictiveIntelligenceEngine:
    """Probabilistic forward state, intentionally advisory and non-executing."""

    def predict(
        self,
        *,
        current_price: float,
        atr: float,
        confidence: float,
        trend_strength: float,
        momentum_score: float,
        trap_probability: float,
        regime: str,
        side: str,
    ) -> dict[str, Any]:
        directional_bias = 1.0 if str(side).upper() == "BUY" else -1.0
        regime_bonus = 0.10 if str(regime).upper() in {"TRENDING", "EXPANSION", "HIGH_VOLATILITY"} else 0.0
        breakout_probability = _clamp((confidence * 0.34) + (trend_strength * 0.25) + (momentum_score * 0.26) + regime_bonus - (trap_probability * 0.18), 0.0, 1.0)
        fakeout_probability = _clamp((trap_probability * 0.55) + ((1.0 - confidence) * 0.25) + ((1.0 - trend_strength) * 0.20), 0.0, 1.0)
        exhaustion_probability = _clamp((momentum_score * 0.25) + (trap_probability * 0.45) + ((1.0 - trend_strength) * 0.18), 0.0, 1.0)
        expansion_probability = _clamp((momentum_score * 0.34) + (trend_strength * 0.24) + (breakout_probability * 0.30), 0.0, 1.0)
        volatility_range = max(float(atr), float(current_price) * 0.0015)
        cone = [
            {
                "horizon": horizon,
                "low": round(current_price - (volatility_range * scale), 8),
                "mid": round(current_price + (directional_bias * volatility_range * scale * (breakout_probability - fakeout_probability)), 8),
                "high": round(current_price + (volatility_range * scale), 8),
            }
            for horizon, scale in (("5m", 0.8), ("15m", 1.35), ("1h", 2.2))
        ]
        return {
            "breakout_probability": round(breakout_probability * 100, 2),
            "liquidity_target_zones": self._targets(current_price, volatility_range, directional_bias),
            "exhaustion_probability": round(exhaustion_probability * 100, 2),
            "fakeout_probability": round(fakeout_probability * 100, 2),
            "volatility_expansion_probability": round(expansion_probability * 100, 2),
            "trend_continuation_likelihood": round(_clamp((breakout_probability * 0.68) + (trend_strength * 0.32), 0.0, 1.0) * 100, 2),
            "confidence_cones": cone,
        }

    @staticmethod
    def _targets(current_price: float, volatility_range: float, directional_bias: float) -> list[dict[str, Any]]:
        return [
            {
                "label": f"LQ-{index}",
                "price": round(current_price + (directional_bias * volatility_range * multiplier), 8),
                "probability": round(max(0.25, 0.74 - (index * 0.13)) * 100, 2),
            }
            for index, multiplier in enumerate((1.0, 1.8, 2.7), start=1)
        ]


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))
