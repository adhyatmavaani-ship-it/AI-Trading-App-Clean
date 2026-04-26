from __future__ import annotations

import math

import pandas as pd

from app.trading.strategies.base import BaseStrategy, StrategyDecision


class HybridCryptoStrategy(BaseStrategy):
    name = "hybrid_crypto"

    def __init__(
        self,
        trend_fast_period: int = 50,
        trend_slow_period: int = 200,
        rsi_period: int = 14,
        breakout_lookback: int = 20,
        volume_window: int = 20,
        min_volume_spike: float = 1.4,
        swing_lookback: int = 10,
    ):
        self.trend_fast_period = trend_fast_period
        self.trend_slow_period = trend_slow_period
        self.rsi_period = rsi_period
        self.breakout_lookback = breakout_lookback
        self.volume_window = volume_window
        self.min_volume_spike = min_volume_spike
        self.swing_lookback = swing_lookback

    def evaluate(
        self,
        data: pd.DataFrame | dict[str, pd.DataFrame],
        parameters: dict[str, int | float] | None = None,
    ) -> StrategyDecision:
        parameters = parameters or {}
        trend_fast_period = int(parameters.get("trend_fast_period", self.trend_fast_period))
        trend_slow_period = int(parameters.get("trend_slow_period", self.trend_slow_period))
        rsi_period = int(parameters.get("rsi_period", self.rsi_period))
        breakout_lookback = int(parameters.get("breakout_lookback", self.breakout_lookback))
        volume_window = int(parameters.get("volume_window", self.volume_window))
        min_volume_spike = float(parameters.get("min_volume_spike", self.min_volume_spike))
        swing_lookback = int(parameters.get("swing_lookback", self.swing_lookback))
        lower_frame, higher_frame = self._resolve_frames(data)
        if len(lower_frame) < max(breakout_lookback + 2, rsi_period + 2):
            return self._hold("insufficient_lower_timeframe_data")
        if len(higher_frame) < trend_slow_period + 2:
            return self._hold("insufficient_higher_timeframe_data")

        trend_signal, trend_strength = self._trend_signal(higher_frame, trend_fast_period, trend_slow_period)
        if trend_signal == "HOLD":
            return self._hold("no_higher_timeframe_trend")

        rsi_series = self._rsi_series(lower_frame["close"].astype(float), rsi_period)
        if rsi_series.empty or pd.isna(rsi_series.iloc[-1]):
            return self._hold("rsi_unavailable")
        current_rsi = float(rsi_series.iloc[-1])
        recent_rsi = rsi_series.tail(12).dropna()
        pullback_rsi = float(recent_rsi.min()) if trend_signal == "BUY" else float(recent_rsi.max())

        breakout_signal, breakout_strength = self._breakout_signal(lower_frame, breakout_lookback)
        if breakout_signal != trend_signal:
            return self._hold("breakout_not_aligned")

        entry_ready, rsi_score = self._rsi_pullback_score(trend_signal, pullback_rsi)
        if not entry_ready:
            return self._hold("pullback_not_ready")

        volume_ratio = self._volume_ratio(lower_frame, volume_window)
        if volume_ratio < min_volume_spike:
            return self._hold("volume_confirmation_missing")
        volume_score = min(1.0, volume_ratio / max(min_volume_spike * 1.5, 1e-8))

        confidence = (
            0.45 * trend_strength
            + 0.25 * rsi_score
            + 0.20 * breakout_strength
            + 0.10 * volume_score
        )
        stop_loss = self._swing_stop_loss(lower_frame, trend_signal, swing_lookback)
        current_price = float(lower_frame["close"].astype(float).iloc[-1])
        risk_distance = abs(current_price - stop_loss)
        if risk_distance <= 0:
            return self._hold("invalid_stop_loss")
        take_profit = (
            current_price + (risk_distance * 2)
            if trend_signal == "BUY"
            else current_price - (risk_distance * 2)
        )

        return self._decision(
            trend_signal,
            min(0.99, confidence),
            trend_strength=round(trend_strength, 6),
            rsi=round(current_rsi, 4),
            pullback_rsi=round(pullback_rsi, 4),
            rsi_score=round(rsi_score, 6),
            breakout_strength=round(breakout_strength, 6),
            volume_ratio=round(volume_ratio, 6),
            stop_loss=round(stop_loss, 8),
            take_profit=round(take_profit, 8),
            risk_reward_ratio="2.0",
            trend_fast_period=trend_fast_period,
            trend_slow_period=trend_slow_period,
            rsi_period=rsi_period,
            breakout_lookback=breakout_lookback,
        )

    def _resolve_frames(
        self,
        data: pd.DataFrame | dict[str, pd.DataFrame],
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        if isinstance(data, dict):
            lower_frame = data.get("5m")
            if lower_frame is None:
                lower_frame = data.get("15m")
            if lower_frame is None:
                lower_frame = next(iter(data.values()))
            higher_frame = data.get("1h")
            if higher_frame is None:
                higher_frame = data.get("15m")
            if higher_frame is None:
                higher_frame = self._derive_higher_timeframe(lower_frame)
            return lower_frame.copy(), higher_frame.copy()
        frame = data.copy()
        return frame, self._derive_higher_timeframe(frame)

    def _derive_higher_timeframe(self, frame: pd.DataFrame) -> pd.DataFrame:
        working = frame.copy()
        if "timestamp" in working.columns:
            ts = pd.to_datetime(working["timestamp"], utc=True)
        elif "open_time" in working.columns:
            ts = pd.to_datetime(working["open_time"], unit="ms", utc=True)
        else:
            ts = pd.date_range(end=pd.Timestamp.now(tz="UTC"), periods=len(working), freq="5min")
        working.index = ts
        aggregated = pd.DataFrame(
            {
                "open": working["open"].astype(float).resample("1h").first(),
                "high": working["high"].astype(float).resample("1h").max(),
                "low": working["low"].astype(float).resample("1h").min(),
                "close": working["close"].astype(float).resample("1h").last(),
                "volume": working["volume"].astype(float).resample("1h").sum(),
            }
        ).dropna()
        if aggregated.empty:
            return working.reset_index(drop=True)
        return aggregated.reset_index(drop=True)

    def _trend_signal(self, frame: pd.DataFrame, trend_fast_period: int, trend_slow_period: int) -> tuple[str, float]:
        closes = frame["close"].astype(float)
        ema_fast = closes.ewm(span=trend_fast_period, adjust=False).mean()
        ema_slow = closes.ewm(span=trend_slow_period, adjust=False).mean()
        current_fast = float(ema_fast.iloc[-1])
        current_slow = float(ema_slow.iloc[-1])
        current_close = float(closes.iloc[-1])
        spread = (current_fast - current_slow) / max(current_close, 1e-8)
        strength = min(1.0, abs(spread) * 120)
        if current_fast > current_slow:
            return "BUY", max(0.2, strength)
        if current_fast < current_slow:
            return "SELL", max(0.2, strength)
        return "HOLD", 0.0

    def _rsi_series(self, closes: pd.Series, period: int) -> pd.Series:
        delta = closes.diff()
        gains = delta.clip(lower=0.0)
        losses = -delta.clip(upper=0.0)
        avg_gain = gains.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        avg_loss = losses.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0.0, 1e-8)
        return 100 - (100 / (1 + rs))

    def _breakout_signal(self, frame: pd.DataFrame, breakout_lookback: int) -> tuple[str, float]:
        highs = frame["high"].astype(float)
        lows = frame["low"].astype(float)
        closes = frame["close"].astype(float)
        breakout_high = highs.rolling(breakout_lookback).max().shift(1).iloc[-1]
        breakout_low = lows.rolling(breakout_lookback).min().shift(1).iloc[-1]
        current_close = float(closes.iloc[-1])
        current_range = max(float((highs - lows).rolling(breakout_lookback).mean().iloc[-1] or 0.0), current_close * 0.003)
        if pd.notna(breakout_high) and current_close > float(breakout_high):
            strength = min(1.0, (current_close - float(breakout_high)) / max(current_range, 1e-8))
            return "BUY", max(0.25, strength)
        if pd.notna(breakout_low) and current_close < float(breakout_low):
            strength = min(1.0, (float(breakout_low) - current_close) / max(current_range, 1e-8))
            return "SELL", max(0.25, strength)
        return "HOLD", 0.0

    def _rsi_pullback_score(self, trend_signal: str, rsi_value: float) -> tuple[bool, float]:
        if trend_signal == "BUY":
            if not 40.0 <= rsi_value <= 65.0:
                return False, 0.0
            distance = abs(rsi_value - 52.0)
            return True, max(0.2, 1.0 - distance / 18.0)
        if not 35.0 <= rsi_value <= 60.0:
            return False, 0.0
        distance = abs(rsi_value - 48.0)
        return True, max(0.2, 1.0 - distance / 18.0)

    def _volume_ratio(self, frame: pd.DataFrame, volume_window: int) -> float:
        volume = frame["volume"].astype(float)
        baseline = float(volume.rolling(volume_window).mean().iloc[-2] or 0.0)
        current = float(volume.iloc[-1])
        return current / max(baseline, 1e-8)

    def _swing_stop_loss(self, frame: pd.DataFrame, signal: str, swing_lookback: int) -> float:
        highs = frame["high"].astype(float).tail(swing_lookback)
        lows = frame["low"].astype(float).tail(swing_lookback)
        if signal == "BUY":
            return float(lows.min())
        return float(highs.max())
