from __future__ import annotations

import pandas as pd

from app.trading.strategies.base import BaseStrategy, StrategyDecision


class EMACrossoverStrategy(BaseStrategy):
    name = "ema_crossover"

    def __init__(self, fast_period: int = 12, slow_period: int = 26):
        self.fast_period = fast_period
        self.slow_period = slow_period

    def evaluate(
        self,
        data: pd.DataFrame,
        parameters: dict[str, int | float] | None = None,
    ) -> StrategyDecision:
        parameters = parameters or {}
        fast_period = int(parameters.get("ema_fast_period", self.fast_period))
        slow_period = int(parameters.get("ema_slow_period", self.slow_period))
        if fast_period <= 0 or slow_period <= fast_period:
            return self._hold("invalid_ema_parameters")
        if len(data) < slow_period + 2:
            return self._hold("insufficient_data")

        closes = data["close"].astype(float)
        fast = closes.ewm(span=fast_period, adjust=False).mean()
        slow = closes.ewm(span=slow_period, adjust=False).mean()
        prev_fast, curr_fast = float(fast.iloc[-2]), float(fast.iloc[-1])
        prev_slow, curr_slow = float(slow.iloc[-2]), float(slow.iloc[-1])
        current_price = float(closes.iloc[-1])
        spread_pct = abs(curr_fast - curr_slow) / max(current_price, 1e-8)
        confidence = min(0.95, 0.45 + spread_pct * 40)

        if prev_fast <= prev_slow and curr_fast > curr_slow:
            return self._decision(
                "BUY",
                confidence,
                fast_ema=round(curr_fast, 8),
                slow_ema=round(curr_slow, 8),
                ema_fast_period=fast_period,
                ema_slow_period=slow_period,
            )
        if prev_fast >= prev_slow and curr_fast < curr_slow:
            return self._decision(
                "SELL",
                confidence,
                fast_ema=round(curr_fast, 8),
                slow_ema=round(curr_slow, 8),
                ema_fast_period=fast_period,
                ema_slow_period=slow_period,
            )
        return self._hold("no_crossover")
