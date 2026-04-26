from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import ta


@dataclass(frozen=True)
class MarketRegimeState:
    regime: str
    adx: float
    atr: float
    confidence_multiplier: float


class MarketRegimeDetector:
    def __init__(self, adx_period: int = 14):
        self.adx_period = adx_period

    def detect(self, frame: pd.DataFrame) -> MarketRegimeState:
        if len(frame) < self.adx_period + 5:
            return MarketRegimeState(
                regime="RANGING",
                adx=0.0,
                atr=0.0,
                confidence_multiplier=0.55,
            )

        high = frame["high"].astype(float)
        low = frame["low"].astype(float)
        close = frame["close"].astype(float)
        adx_indicator = ta.trend.ADXIndicator(high=high, low=low, close=close, window=self.adx_period)
        atr_indicator = ta.volatility.AverageTrueRange(high=high, low=low, close=close, window=self.adx_period)
        adx = float(adx_indicator.adx().iloc[-1])
        atr = float(atr_indicator.average_true_range().iloc[-1])

        if adx > 25.0:
            regime = "TRENDING"
            multiplier = min(1.0, 0.8 + ((adx - 25.0) / 50.0))
        elif adx < 20.0:
            regime = "RANGING"
            multiplier = max(0.35, adx / 40.0)
        else:
            regime = "RANGING"
            multiplier = 0.6

        return MarketRegimeState(
            regime=regime,
            adx=adx,
            atr=atr,
            confidence_multiplier=multiplier,
        )
