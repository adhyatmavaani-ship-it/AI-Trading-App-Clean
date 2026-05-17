from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class RegimeIntelligence:
    regime: str
    confidence: float
    transition_probability: float
    strategy_suitability: dict[str, float]
    ai_modifiers: dict[str, float | str]
    reasons: list[str]


class MarketRegimeEngine:
    def analyze(self, frame: pd.DataFrame | None) -> RegimeIntelligence:
        if frame is None or getattr(frame, "empty", True) or len(frame) < 8:
            return RegimeIntelligence(
                regime="UNKNOWN",
                confidence=0.0,
                transition_probability=0.0,
                strategy_suitability={},
                ai_modifiers={"risk_multiplier": 0.0, "assistant_bias": "WAIT"},
                reasons=["insufficient_candles"],
            )
        closes = frame["close"].astype(float)
        highs = frame["high"].astype(float)
        lows = frame["low"].astype(float)
        volumes = frame["volume"].astype(float)
        price = max(float(closes.iloc[-1]), 1e-8)
        returns = closes.pct_change().dropna()
        volatility = float(returns.tail(24).std(ddof=0) or 0.0)
        range_ratio = (float(highs.tail(24).max()) - float(lows.tail(24).min())) / price
        slope = (float(closes.iloc[-1]) - float(closes.iloc[max(0, len(closes) - 12)])) / price
        avg_volume = float(volumes.tail(min(len(volumes), 20)).mean() or 0.0)
        volume_ratio = float(volumes.iloc[-1]) / max(avg_volume, 1e-8)
        compression = range_ratio < 0.012 and volatility < 0.006
        expansion = range_ratio > 0.032 or volatility > 0.022
        reasons: list[str] = []
        if compression:
            regime = "COMPRESSION"
            confidence = 0.68
            reasons.append("range_and_volatility_compressed")
        elif expansion:
            regime = "EXPANSION"
            confidence = 0.72
            reasons.append("volatility_expansion")
        elif abs(slope) > 0.006:
            regime = "TRENDING"
            confidence = 0.66 + min(abs(slope) * 20, 0.20)
            reasons.append("directional_slope")
        elif volume_ratio >= 1.5 and abs(slope) < 0.003:
            regime = "ACCUMULATION" if closes.iloc[-1] >= closes.iloc[0] else "DISTRIBUTION"
            confidence = 0.62
            reasons.append("high_volume_absorption")
        else:
            regime = "RANGING"
            confidence = 0.58
            reasons.append("mean_reverting_rotation")
        transition_probability = min(1.0, (volatility / 0.03) * 0.55 + (volume_ratio / 3.0) * 0.45)
        return RegimeIntelligence(
            regime=regime,
            confidence=round(confidence, 4),
            transition_probability=round(transition_probability, 4),
            strategy_suitability=self._suitability(regime),
            ai_modifiers={
                "risk_multiplier": self._risk_multiplier(regime),
                "assistant_bias": "BREAKOUT" if regime in {"COMPRESSION", "EXPANSION"} else "CONTINUATION" if regime == "TRENDING" else "WAIT",
            },
            reasons=reasons,
        )

    def _suitability(self, regime: str) -> dict[str, float]:
        table: dict[str, dict[str, float]] = {
            "TRENDING": {"momentum": 0.86, "breakout": 0.72, "mean_reversion": 0.28},
            "COMPRESSION": {"momentum": 0.42, "breakout": 0.82, "mean_reversion": 0.55},
            "EXPANSION": {"momentum": 0.78, "breakout": 0.74, "mean_reversion": 0.20},
            "RANGING": {"momentum": 0.32, "breakout": 0.38, "mean_reversion": 0.76},
            "ACCUMULATION": {"momentum": 0.54, "breakout": 0.68, "mean_reversion": 0.48},
            "DISTRIBUTION": {"momentum": 0.48, "breakout": 0.62, "mean_reversion": 0.42},
        }
        return table.get(regime, {})

    def _risk_multiplier(self, regime: str) -> float:
        return {
            "TRENDING": 1.0,
            "COMPRESSION": 0.72,
            "EXPANSION": 0.62,
            "RANGING": 0.70,
            "ACCUMULATION": 0.82,
            "DISTRIBUTION": 0.68,
        }.get(regime, 0.0)
