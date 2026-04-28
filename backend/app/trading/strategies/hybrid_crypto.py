from __future__ import annotations

import math

import pandas as pd
import ta

from app.trading.exits import initial_exit_plan
from app.trading.strategies.base import BaseStrategy, StrategyDecision


class HybridCryptoStrategy(BaseStrategy):
    name = "hybrid_crypto"

    def __init__(
        self,
        structure_lookback: int = 20,
        volume_window: int = 20,
        min_volume_spike: float = 1.5,
        atr_window: int = 14,
        chandelier_multiplier: float = 2.5,
    ):
        self.structure_lookback = structure_lookback
        self.volume_window = volume_window
        self.min_volume_spike = min_volume_spike
        self.atr_window = atr_window
        self.chandelier_multiplier = chandelier_multiplier

    def evaluate(
        self,
        data: pd.DataFrame | dict[str, pd.DataFrame],
        parameters: dict[str, int | float] | None = None,
    ) -> StrategyDecision:
        parameters = parameters or {}
        structure_lookback = int(parameters.get("structure_lookback", self.structure_lookback))
        volume_window = int(parameters.get("volume_window", self.volume_window))
        min_volume_spike = float(parameters.get("min_volume_spike", self.min_volume_spike))
        atr_window = int(parameters.get("atr_window", self.atr_window))
        chandelier_multiplier = float(parameters.get("chandelier_multiplier", self.chandelier_multiplier))

        lower_frame, higher_frame = self._resolve_frames(data)
        if len(lower_frame) < max(structure_lookback + 5, volume_window + 3, atr_window + 3):
            return self._hold("insufficient_lower_timeframe_data")
        if len(higher_frame) < structure_lookback + 3:
            return self._hold("insufficient_higher_timeframe_data")

        structure_signal, structure_strength = self._structure_signal(higher_frame, structure_lookback)
        if structure_signal == "HOLD":
            return self._hold("no_structure_break")

        mfi_series = self._mfi_series(lower_frame)
        if mfi_series.empty or pd.isna(mfi_series.iloc[-1]):
            return self._hold("mfi_unavailable")
        current_mfi = float(mfi_series.iloc[-1])
        momentum_signal, momentum_strength, momentum_penalty = self._momentum_signal(structure_signal, current_mfi)
        if momentum_signal != structure_signal:
            return self._hold("momentum_not_aligned")

        divergence_penalty, divergence_flag = self._divergence_penalty(
            lower_frame["close"].astype(float),
            mfi_series,
            structure_signal,
        )
        if divergence_penalty >= 0.18:
            return self._hold("mfi_divergence_warning")

        volume_ratio = self._volume_ratio(lower_frame, volume_window)
        if volume_ratio < min_volume_spike:
            return self._hold("volume_confirmation_missing")
        volume_score = min(1.0, volume_ratio / max(min_volume_spike * 1.5, 1e-8))

        current_price = float(lower_frame["close"].astype(float).iloc[-1])
        atr = self._atr(lower_frame, atr_window)
        if atr <= 0:
            return self._hold("atr_unavailable")

        stop_loss_multiplier = float(parameters.get("stop_loss_multiplier", 1.0))
        volatility = self._volatility(lower_frame)
        exit_plan = initial_exit_plan(
            side=structure_signal,
            entry_price=current_price,
            atr=atr,
            volatility=volatility,
            stop_loss_multiplier=stop_loss_multiplier,
        )
        stop_loss = float(exit_plan.stop_loss)
        if not math.isfinite(stop_loss):
            return self._hold("invalid_stop_loss")
        risk_distance = abs(current_price - stop_loss)
        if risk_distance <= 0:
            return self._hold("invalid_stop_loss")

        trailing_sl = (
            current_price * (1.0 - float(exit_plan.trailing_stop_pct))
            if structure_signal == "BUY"
            else current_price * (1.0 + float(exit_plan.trailing_stop_pct))
        )
        if not math.isfinite(trailing_sl):
            return self._hold("invalid_trailing_stop")

        liquidity_sweep = self._liquidity_sweep_signal(lower_frame, structure_signal, structure_lookback, min_volume_spike)

        confidence = (
            0.40 * structure_strength
            + 0.25 * momentum_strength
            + 0.20 * volume_score
            + 0.15 * (1.0 if liquidity_sweep else 0.0)
        )
        confidence = max(0.0, min(0.98, confidence - divergence_penalty - momentum_penalty))

        reason_parts = [
            "Structure breakout",
            "MFI momentum",
            "volume confirmation",
        ]
        if liquidity_sweep:
            reason_parts.append("liquidity sweep reversal")
        if divergence_flag:
            reason_parts.append("minor MFI divergence penalty")

        return self._decision(
            structure_signal,
            confidence,
            reason=" + ".join(reason_parts),
            structure_signal=structure_signal,
            structure_strength=round(structure_strength, 6),
            mfi=round(current_mfi, 4),
            mfi_strength=round(momentum_strength, 6),
            mfi_extreme_penalty=round(momentum_penalty, 6),
            volume_ratio=round(volume_ratio, 6),
            divergence_penalty=round(divergence_penalty, 6),
            liquidity_sweep="true" if liquidity_sweep else "false",
            stop_loss=round(stop_loss, 8),
            trailing_sl=round(trailing_sl, 8),
            take_profit=round(float(exit_plan.take_profit), 8),
            risk_reward_ratio="dynamic",
            structure_lookback=structure_lookback,
            atr=round(atr, 8),
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

    def _structure_signal(self, frame: pd.DataFrame, lookback: int) -> tuple[str, float]:
        highs = frame["high"].astype(float)
        lows = frame["low"].astype(float)
        closes = frame["close"].astype(float)
        current_high = float(highs.iloc[-1])
        current_low = float(lows.iloc[-1])
        previous_high = float(highs.tail(lookback + 1).iloc[:-1].max())
        previous_low = float(lows.tail(lookback + 1).iloc[:-1].min())
        current_close = float(closes.iloc[-1])

        if current_high > previous_high and self._higher_high_sequence(frame):
            strength = min(1.0, (current_close - previous_high) / max(current_close * 0.02, 1e-8))
            return "BUY", max(0.55, strength)
        if current_low < previous_low and self._lower_low_sequence(frame):
            strength = min(1.0, (previous_low - current_close) / max(current_close * 0.02, 1e-8))
            return "SELL", max(0.55, strength)
        return "HOLD", 0.0

    def _higher_high_sequence(self, frame: pd.DataFrame, candles: int = 4) -> bool:
        highs = frame["high"].astype(float).tail(candles).tolist()
        lows = frame["low"].astype(float).tail(candles).tolist()
        return all(curr >= prev for prev, curr in zip(highs, highs[1:], strict=False)) and all(curr >= prev for prev, curr in zip(lows, lows[1:], strict=False))

    def _lower_low_sequence(self, frame: pd.DataFrame, candles: int = 4) -> bool:
        highs = frame["high"].astype(float).tail(candles).tolist()
        lows = frame["low"].astype(float).tail(candles).tolist()
        return all(curr <= prev for prev, curr in zip(highs, highs[1:], strict=False)) and all(curr <= prev for prev, curr in zip(lows, lows[1:], strict=False))

    def _mfi_series(self, frame: pd.DataFrame, window: int = 14) -> pd.Series:
        return ta.volume.money_flow_index(
            high=frame["high"].astype(float),
            low=frame["low"].astype(float),
            close=frame["close"].astype(float),
            volume=frame["volume"].astype(float),
            window=window,
        )

    def _momentum_signal(self, structure_signal: str, mfi_value: float) -> tuple[str, float, float]:
        if structure_signal == "BUY":
            if mfi_value <= 50.0:
                return "HOLD", 0.0, 0.0
            strength = max(0.35, min(1.0, (mfi_value - 50.0) / 20.0))
            penalty = 0.08 if mfi_value >= 80.0 else 0.0
            return "BUY", strength, penalty
        if mfi_value >= 50.0:
            return "HOLD", 0.0, 0.0
        strength = max(0.35, min(1.0, (50.0 - mfi_value) / 20.0))
        penalty = 0.08 if mfi_value <= 20.0 else 0.0
        return "SELL", strength, penalty

    def _divergence_penalty(self, closes: pd.Series, mfi_series: pd.Series, signal: str) -> tuple[float, bool]:
        recent_close = closes.tail(5).astype(float)
        recent_mfi = mfi_series.tail(5).astype(float)
        if len(recent_close) < 5 or len(recent_mfi) < 5:
            return 0.0, False
        price_change = float(recent_close.iloc[-1] - recent_close.iloc[0])
        mfi_change = float(recent_mfi.iloc[-1] - recent_mfi.iloc[0])
        if signal == "BUY" and price_change > 0 and mfi_change < 0:
            return 0.12, True
        if signal == "SELL" and price_change < 0 and mfi_change > 0:
            return 0.12, True
        return 0.0, False

    def _volume_ratio(self, frame: pd.DataFrame, volume_window: int) -> float:
        volume = frame["volume"].astype(float)
        baseline = float(volume.rolling(volume_window).mean().iloc[-2] or 0.0)
        current = float(volume.iloc[-1])
        return current / max(baseline, 1e-8)

    def _atr(self, frame: pd.DataFrame, window: int) -> float:
        atr_series = ta.volatility.average_true_range(
            high=frame["high"].astype(float),
            low=frame["low"].astype(float),
            close=frame["close"].astype(float),
            window=window,
        )
        atr_value = float(atr_series.iloc[-1]) if not atr_series.empty else 0.0
        return max(0.0, atr_value)

    def _volatility(self, frame: pd.DataFrame, window: int = 20) -> float:
        returns = frame["close"].astype(float).pct_change().dropna()
        if returns.empty:
            return 0.0
        return float(returns.tail(window).std() or 0.0)

    def _liquidity_sweep_signal(
        self,
        frame: pd.DataFrame,
        signal: str,
        lookback: int,
        min_volume_spike: float,
    ) -> bool:
        if len(frame) < lookback + 4:
            return False
        recent = frame.tail(3).reset_index(drop=True)
        prior = frame.iloc[: -3]
        prior_high = float(prior["high"].astype(float).tail(lookback).max())
        prior_low = float(prior["low"].astype(float).tail(lookback).min())
        volume_ratio = self._volume_ratio(frame, min(lookback, self.volume_window))
        if volume_ratio < min_volume_spike:
            return False

        if signal == "BUY":
            swept = float(recent["low"].min()) < prior_low
            reclaimed = float(recent["close"].iloc[-1]) > prior_low
            return swept and reclaimed
        swept = float(recent["high"].max()) > prior_high
        reclaimed = float(recent["close"].iloc[-1]) < prior_high
        return swept and reclaimed
