from __future__ import annotations

import pandas as pd

from app.trading.strategies.base import BaseStrategy, StrategyDecision


class BreakoutStrategy(BaseStrategy):
    name = "breakout"

    def __init__(self, lookback: int = 20):
        self.lookback = lookback

    def evaluate(
        self,
        data: pd.DataFrame,
        parameters: dict[str, int | float] | None = None,
    ) -> StrategyDecision:
        parameters = parameters or {}
        lookback = int(parameters.get("breakout_lookback", self.lookback))
        if lookback <= 1:
            return self._hold("invalid_breakout_parameters")
        if len(data) < lookback + 2:
            return self._hold("insufficient_data")

        highs = data["high"].astype(float)
        lows = data["low"].astype(float)
        closes = data["close"].astype(float)
        previous_high = highs.rolling(lookback).max().shift(1)
        previous_low = lows.rolling(lookback).min().shift(1)
        current_close = float(closes.iloc[-1])
        breakout_high = float(previous_high.iloc[-1])
        breakout_low = float(previous_low.iloc[-1])
        average_range = float((highs - lows).rolling(lookback).mean().iloc[-1] or 0.0)
        normalized_range = max(average_range, current_close * 0.002, 1e-8)

        if current_close > breakout_high:
            confidence = min(0.98, 0.45 + (current_close - breakout_high) / normalized_range)
            return self._decision(
                "BUY",
                confidence,
                breakout_level=round(breakout_high, 8),
                breakout_lookback=lookback,
            )
        if current_close < breakout_low:
            confidence = min(0.98, 0.45 + (breakout_low - current_close) / normalized_range)
            return self._decision(
                "SELL",
                confidence,
                breakout_level=round(breakout_low, 8),
                breakout_lookback=lookback,
            )
        return self._hold("inside_range")
