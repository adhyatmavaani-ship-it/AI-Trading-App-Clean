from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class OrderflowSnapshot:
    liquidity_pressure_score: float
    directional_aggression_score: float
    trap_probability: float
    absorption_zones: list[dict[str, Any]]
    execution_quality: dict[str, Any]
    momentum: float
    reasons: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "liquidity_pressure_score": round(self.liquidity_pressure_score * 100, 2),
            "directional_aggression_score": round(self.directional_aggression_score * 100, 2),
            "trap_probability": round(self.trap_probability * 100, 2),
            "absorption_zones": self.absorption_zones,
            "execution_quality": self.execution_quality,
            "momentum": round(self.momentum * 100, 2),
            "reasons": self.reasons,
        }


class InstitutionalOrderflowEngine:
    """Low-latency orderflow proxy using OHLCV now, tick/orderbook inputs later."""

    def analyze(
        self,
        frame: pd.DataFrame | None,
        *,
        spread_bps: float = 0.0,
        orderbook: dict[str, Any] | None = None,
    ) -> OrderflowSnapshot:
        if frame is None or getattr(frame, "empty", True):
            return OrderflowSnapshot(0.0, 0.0, 0.0, [], {"state": "NO_DATA"}, 0.0, ["no market frame"])

        recent = frame.tail(min(len(frame), 48)).copy()
        for column in ("open", "high", "low", "close", "volume"):
            recent[column] = recent[column].astype(float)
        close = recent["close"]
        volume = recent["volume"]
        ranges = (recent["high"] - recent["low"]).abs()
        body = (recent["close"] - recent["open"]).abs()
        signed_volume = ((recent["close"] >= recent["open"]).astype(float) * 2.0 - 1.0) * volume

        avg_volume = float(volume.tail(min(len(volume), 20)).mean() or 0.0)
        volume_ratio = float(volume.iloc[-1]) / max(avg_volume, 1e-8)
        net_delta = float(signed_volume.tail(min(len(signed_volume), 12)).sum())
        gross_volume = float(volume.tail(min(len(volume), 12)).sum() or 0.0)
        aggression = _clamp(abs(net_delta) / max(gross_volume, 1e-8), 0.0, 1.0)
        direction = 1.0 if net_delta >= 0 else -1.0

        wick_ratio = _clamp(float((ranges.iloc[-1] - body.iloc[-1]) / max(ranges.iloc[-1], 1e-8)), 0.0, 1.0)
        pressure = _orderbook_pressure(orderbook)
        if pressure == 0.0:
            pressure = _clamp((aggression * 0.55) + (min(volume_ratio, 2.5) / 2.5 * 0.45), 0.0, 1.0)

        absorption = self._absorption_zones(recent, volume_ratio=volume_ratio, direction=direction)
        trap_probability = _clamp((wick_ratio * 0.48) + ((1.0 - aggression) * 0.22) + (min(spread_bps, 25.0) / 25.0 * 0.30), 0.0, 1.0)
        momentum = _clamp(abs(float(close.iloc[-1] - close.iloc[max(0, len(close) - 6)])) / max(float(close.iloc[-1]) * 0.01, 1e-8), 0.0, 1.0)
        reasons = []
        if volume_ratio >= 1.35:
            reasons.append("high relative volume")
        if aggression >= 0.38:
            reasons.append("directional aggressive flow")
        if absorption:
            reasons.append("absorption zone detected")
        if trap_probability >= 0.55:
            reasons.append("trap risk elevated")
        if not reasons:
            reasons.append("balanced orderflow")

        return OrderflowSnapshot(
            liquidity_pressure_score=pressure,
            directional_aggression_score=aggression * direction,
            trap_probability=trap_probability,
            absorption_zones=absorption,
            execution_quality={
                "state": "DEGRADED" if spread_bps >= 18 or trap_probability >= 0.70 else "NORMAL",
                "spread_bps": round(float(spread_bps), 4),
                "volume_ratio": round(volume_ratio, 4),
                "aggressive_side": "BUY" if direction >= 0 else "SELL",
            },
            momentum=momentum,
            reasons=reasons,
        )

    def _absorption_zones(self, recent: pd.DataFrame, *, volume_ratio: float, direction: float) -> list[dict[str, Any]]:
        if len(recent) < 8:
            return []
        latest = recent.iloc[-1]
        candle_range = abs(float(latest["high"] - latest["low"]))
        body = abs(float(latest["close"] - latest["open"]))
        if volume_ratio < 1.25 or candle_range <= 0 or (body / candle_range) > 0.42:
            return []
        return [
            {
                "side": "BID" if direction < 0 else "ASK",
                "low": round(float(latest["low"]), 8),
                "high": round(float(latest["high"]), 8),
                "confidence": round(min(volume_ratio / 2.2, 1.0) * 100, 2),
                "reason": "large volume with muted candle body",
            }
        ]


def _orderbook_pressure(orderbook: dict[str, Any] | None) -> float:
    if not orderbook:
        return 0.0
    bid_depth = float(orderbook.get("bid_depth", 0.0) or 0.0)
    ask_depth = float(orderbook.get("ask_depth", 0.0) or 0.0)
    total = bid_depth + ask_depth
    if total <= 0:
        return 0.0
    return _clamp(abs(bid_depth - ask_depth) / total, 0.0, 1.0)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))
