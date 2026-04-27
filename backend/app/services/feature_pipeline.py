from __future__ import annotations

import logging
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import ta

from app.schemas.trading import FeatureSnapshot
from app.services.regime_detector import RegimeDetector

logger = logging.getLogger(__name__)


class FeaturePipeline:
    """Transforms raw market snapshots into model-ready features."""

    def __init__(self, regime_detector: RegimeDetector | None = None):
        self.regime_detector = regime_detector or RegimeDetector()

    def build(self, symbol: str, frames: dict[str, pd.DataFrame], order_book: dict) -> FeatureSnapshot:
        feature_map: dict[str, float] = {}

        latest_price = 0.0
        realized_vol = 0.0
        atr_value = 0.0

        for timeframe, frame in frames.items():
            df = frame.copy()
            df["rsi"] = ta.momentum.rsi(df["close"], window=14)
            df["mfi"] = ta.volume.money_flow_index(
                high=df["high"],
                low=df["low"],
                close=df["close"],
                volume=df["volume"],
                window=14,
            )
            macd = ta.trend.MACD(df["close"])
            df["macd"] = macd.macd_diff()
            df["ema_fast"] = ta.trend.ema_indicator(df["close"], window=9)
            df["ema_slow"] = ta.trend.ema_indicator(df["close"], window=21)
            df["ema_50"] = ta.trend.ema_indicator(df["close"], window=50)
            df["ema_200"] = ta.trend.ema_indicator(df["close"], window=200)
            df["adx"] = ta.trend.ADXIndicator(df["high"], df["low"], df["close"], window=14).adx()
            df["atr"] = ta.volatility.average_true_range(df["high"], df["low"], df["close"])
            df["avg_atr"] = df["atr"].rolling(20).mean()
            df["returns"] = df["close"].pct_change()
            df["volume_avg_20"] = df["volume"].rolling(20).mean()
            latest = df.iloc[-1]
            latest_price = float(latest["close"])
            realized_vol = float(df["returns"].rolling(20).std().iloc[-1] * np.sqrt(20))
            atr_value = float(latest["atr"])
            structure_lookback = self._structure_lookback(timeframe, len(df))
            bullish_bos, bearish_bos = self._structure_break_flags(df, structure_lookback)
            feature_map.update(
                {
                    f"{timeframe}_rsi": float(latest["rsi"]),
                    f"{timeframe}_mfi": float(latest["mfi"]) if not pd.isna(latest["mfi"]) else 50.0,
                    f"{timeframe}_macd": float(latest["macd"]),
                    f"{timeframe}_ema_spread": float(latest["ema_fast"] - latest["ema_slow"]),
                    f"{timeframe}_ema_fast": float(latest["ema_fast"]) if not pd.isna(latest["ema_fast"]) else float(latest["close"]),
                    f"{timeframe}_ema_slow": float(latest["ema_slow"]) if not pd.isna(latest["ema_slow"]) else float(latest["close"]),
                    f"{timeframe}_ema_50": float(latest["ema_50"]) if not pd.isna(latest["ema_50"]) else float(latest["ema_fast"]),
                    f"{timeframe}_ema_200": float(latest["ema_200"]) if not pd.isna(latest["ema_200"]) else float(latest["ema_slow"]),
                    f"{timeframe}_adx": float(latest["adx"]),
                    f"{timeframe}_atr": atr_value,
                    f"{timeframe}_avg_atr": float(latest["avg_atr"]) if not pd.isna(latest["avg_atr"]) else atr_value,
                    f"{timeframe}_volume": float(latest["volume"]),
                    f"{timeframe}_volume_avg_20": float(latest["volume_avg_20"]) if not pd.isna(latest["volume_avg_20"]) else float(latest["volume"]),
                    f"{timeframe}_return": float(latest["returns"]),
                    f"{timeframe}_structure_bullish": 1.0 if bullish_bos else 0.0,
                    f"{timeframe}_structure_bearish": 1.0 if bearish_bos else 0.0,
                    f"{timeframe}_structure_lookback": float(structure_lookback),
                }
            )

        bid_volume = sum(level["qty"] for level in order_book["bids"][:10])
        ask_volume = sum(level["qty"] for level in order_book["asks"][:10])
        imbalance = (bid_volume - ask_volume) / max(bid_volume + ask_volume, 1e-8)
        trend_strength = abs(feature_map.get("15m_ema_spread", 0.0))
        mean_reversion = abs(feature_map.get("5m_rsi", 50.0) - 50.0) / 50.0
        regime, regime_confidence = self.regime_detector.detect_regime(
            {
                "atr": atr_value,
                "avg_atr": float(feature_map.get("15m_avg_atr", feature_map.get("5m_avg_atr", atr_value)) or atr_value),
                "ema_fast": float(feature_map.get("15m_ema_fast", feature_map.get("5m_ema_fast", latest_price)) or latest_price),
                "ema_slow": float(feature_map.get("15m_ema_slow", feature_map.get("5m_ema_slow", latest_price)) or latest_price),
                "price": latest_price,
                "trend_strength": trend_strength,
                "mean_reversion": mean_reversion,
                "volatility": realized_vol,
            }
        )

        feature_map["order_book_imbalance"] = float(imbalance)
        feature_map["volatility"] = float(realized_vol)
        feature_map["atr"] = atr_value
        feature_map["avg_atr"] = float(feature_map.get("15m_avg_atr", feature_map.get("5m_avg_atr", atr_value)) or atr_value)
        feature_map["regime_confidence"] = float(regime_confidence)

        return FeatureSnapshot(
            symbol=symbol,
            price=latest_price,
            timestamp=datetime.now(timezone.utc),
            regime=regime,
            regime_confidence=regime_confidence,
            volatility=realized_vol,
            atr=atr_value,
            order_book_imbalance=imbalance,
            features=feature_map,
        )

    def _structure_lookback(self, timeframe: str, frame_length: int) -> int:
        defaults = {"1m": 18, "5m": 20, "15m": 24, "1h": 30, "4h": 20}
        baseline = defaults.get(str(timeframe), 20)
        return max(5, min(int(baseline), max(frame_length - 2, 5)))

    def _structure_break_flags(self, frame: pd.DataFrame, lookback: int) -> tuple[bool, bool]:
        if len(frame) <= lookback + 1:
            return False, False
        highs = frame["high"].astype(float)
        lows = frame["low"].astype(float)
        current_high = float(highs.iloc[-1])
        current_low = float(lows.iloc[-1])
        prior_high = float(highs.tail(lookback + 1).iloc[:-1].max())
        prior_low = float(lows.tail(lookback + 1).iloc[:-1].min())
        return current_high > prior_high, current_low < prior_low

