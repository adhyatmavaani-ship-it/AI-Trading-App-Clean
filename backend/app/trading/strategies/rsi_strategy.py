from __future__ import annotations

import pandas as pd

from app.trading.strategies.base import BaseStrategy, StrategyDecision


class RSIStrategy(BaseStrategy):
    name = "rsi"

    def __init__(
        self,
        period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
    ):
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def evaluate(
        self,
        data: pd.DataFrame,
        parameters: dict[str, int | float] | None = None,
    ) -> StrategyDecision:
        parameters = parameters or {}
        period = int(parameters.get("rsi_period", self.period))
        oversold = float(parameters.get("rsi_oversold", self.oversold))
        overbought = float(parameters.get("rsi_overbought", self.overbought))
        if period <= 1 or oversold <= 0 or overbought >= 100 or oversold >= overbought:
            return self._hold("invalid_rsi_parameters")
        if len(data) < period + 2:
            return self._hold("insufficient_data")

        closes = data["close"].astype(float)
        delta = closes.diff()
        gains = delta.clip(lower=0.0)
        losses = -delta.clip(upper=0.0)
        avg_gain = gains.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        avg_loss = losses.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0.0, 1e-8)
        rsi = 100 - (100 / (1 + rs))
        current_rsi = float(rsi.iloc[-1])

        if current_rsi <= oversold:
            confidence = min(0.95, 0.4 + (oversold - current_rsi) / 30)
            return self._decision(
                "BUY",
                confidence,
                rsi=round(current_rsi, 4),
                rsi_period=period,
                rsi_oversold=oversold,
                rsi_overbought=overbought,
            )
        if current_rsi >= overbought:
            confidence = min(0.95, 0.4 + (current_rsi - overbought) / 30)
            return self._decision(
                "SELL",
                confidence,
                rsi=round(current_rsi, 4),
                rsi_period=period,
                rsi_oversold=oversold,
                rsi_overbought=overbought,
            )
        return self._hold("neutral_rsi")
