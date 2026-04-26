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
            macd = ta.trend.MACD(df["close"])
            df["macd"] = macd.macd_diff()
            df["ema_fast"] = ta.trend.ema_indicator(df["close"], window=9)
            df["ema_slow"] = ta.trend.ema_indicator(df["close"], window=21)
            df["adx"] = ta.trend.ADXIndicator(df["high"], df["low"], df["close"], window=14).adx()
            df["atr"] = ta.volatility.average_true_range(df["high"], df["low"], df["close"])
            df["returns"] = df["close"].pct_change()
            latest = df.iloc[-1]
            latest_price = float(latest["close"])
            realized_vol = float(df["returns"].rolling(20).std().iloc[-1] * np.sqrt(20))
            atr_value = float(latest["atr"])
            feature_map.update(
                {
                    f"{timeframe}_rsi": float(latest["rsi"]),
                    f"{timeframe}_macd": float(latest["macd"]),
                    f"{timeframe}_ema_spread": float(latest["ema_fast"] - latest["ema_slow"]),
                    f"{timeframe}_adx": float(latest["adx"]),
                    f"{timeframe}_atr": atr_value,
                    f"{timeframe}_volume": float(latest["volume"]),
                    f"{timeframe}_return": float(latest["returns"]),
                }
            )

        bid_volume = sum(level["qty"] for level in order_book["bids"][:10])
        ask_volume = sum(level["qty"] for level in order_book["asks"][:10])
        imbalance = (bid_volume - ask_volume) / max(bid_volume + ask_volume, 1e-8)
        trend_strength = abs(feature_map.get("15m_ema_spread", 0.0))
        mean_reversion = abs(feature_map.get("5m_rsi", 50.0) - 50.0) / 50.0
        adx_15m = float(feature_map.get("15m_adx", 0.0))
        if adx_15m > 25.0:
            regime, regime_confidence = "TRENDING", min(1.0, 0.75 + (adx_15m - 25.0) / 50.0)
        elif adx_15m < 20.0:
            regime, regime_confidence = "RANGING", max(0.4, adx_15m / 25.0)
        else:
            regime, regime_confidence = self.regime_detector.classify(
                trend_strength=trend_strength,
                volatility=realized_vol,
                mean_reversion=mean_reversion,
            )

        feature_map["order_book_imbalance"] = float(imbalance)
        feature_map["volatility"] = float(realized_vol)
        feature_map["atr"] = atr_value

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

