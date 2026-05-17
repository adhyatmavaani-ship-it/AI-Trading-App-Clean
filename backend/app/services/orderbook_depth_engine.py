from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DepthLevel:
    price: float
    size: float


@dataclass(frozen=True)
class OrderbookAnalytics:
    sequence_id: int
    liquidity_ladder: list[dict[str, Any]]
    pressure_score: float
    imbalance_probability: float
    hidden_liquidity_score: float
    exhaustion_warning: bool
    spoofing_alerts: list[dict[str, Any]]
    iceberg_alerts: list[dict[str, Any]]
    execution_quality: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "sequence_id": self.sequence_id,
            "liquidity_ladder": self.liquidity_ladder,
            "pressure_score": round(self.pressure_score * 100, 2),
            "imbalance_probability": round(self.imbalance_probability * 100, 2),
            "hidden_liquidity_score": round(self.hidden_liquidity_score * 100, 2),
            "exhaustion_warning": self.exhaustion_warning,
            "spoofing_alerts": self.spoofing_alerts,
            "iceberg_alerts": self.iceberg_alerts,
            "execution_quality": self.execution_quality,
        }


class FullDepthOrderbookEngine:
    """Replay-safe L2 orderbook analyzer. It never routes execution."""

    def __init__(self, *, max_depth: int = 50) -> None:
        self.max_depth = max(5, min(int(max_depth), 250))
        self._bids: dict[float, float] = {}
        self._asks: dict[float, float] = {}
        self._sequence_id = 0

    def apply_snapshot(
        self,
        *,
        bids: list[tuple[float, float]],
        asks: list[tuple[float, float]],
        sequence_id: int,
    ) -> OrderbookAnalytics:
        self._bids = self._normalize(bids, reverse=True)
        self._asks = self._normalize(asks, reverse=False)
        self._sequence_id = max(int(sequence_id), self._sequence_id)
        return self.analyze()

    def apply_delta(
        self,
        *,
        bid_updates: list[tuple[float, float]],
        ask_updates: list[tuple[float, float]],
        sequence_id: int,
    ) -> OrderbookAnalytics:
        next_sequence = int(sequence_id)
        if next_sequence <= self._sequence_id:
            return self.analyze()
        self._apply_updates(self._bids, bid_updates)
        self._apply_updates(self._asks, ask_updates)
        self._bids = self._normalize(list(self._bids.items()), reverse=True)
        self._asks = self._normalize(list(self._asks.items()), reverse=False)
        self._sequence_id = next_sequence
        return self.analyze()

    def analyze(self) -> OrderbookAnalytics:
        bids = self._levels(self._bids, reverse=True)
        asks = self._levels(self._asks, reverse=False)
        bid_depth = sum(level.size for level in bids)
        ask_depth = sum(level.size for level in asks)
        total_depth = bid_depth + ask_depth
        imbalance = 0.0 if total_depth <= 0 else (bid_depth - ask_depth) / total_depth
        pressure = min(abs(imbalance), 1.0)
        ladder = self._ladder(bids, asks)
        spoofing = self._spoofing_alerts(ladder)
        iceberg = self._iceberg_alerts(ladder)
        hidden_liquidity = min((len(iceberg) * 0.22) + (pressure * 0.45), 1.0)
        top_bid = bids[0].price if bids else 0.0
        top_ask = asks[0].price if asks else 0.0
        spread_bps = ((top_ask - top_bid) / max((top_ask + top_bid) / 2, 1e-8) * 10000) if top_bid and top_ask else 0.0
        return OrderbookAnalytics(
            sequence_id=self._sequence_id,
            liquidity_ladder=ladder,
            pressure_score=pressure,
            imbalance_probability=min(abs(imbalance) * 1.35, 1.0),
            hidden_liquidity_score=hidden_liquidity,
            exhaustion_warning=total_depth > 0 and min(bid_depth, ask_depth) / total_depth < 0.22,
            spoofing_alerts=spoofing,
            iceberg_alerts=iceberg,
            execution_quality={
                "state": "DEGRADED" if spread_bps >= 18 or spoofing else "NORMAL",
                "spread_bps": round(spread_bps, 4),
                "bid_depth": round(bid_depth, 8),
                "ask_depth": round(ask_depth, 8),
            },
        )

    @staticmethod
    def synthetic_from_price(*, price: float, atr: float, sequence_id: int = 1) -> "FullDepthOrderbookEngine":
        engine = FullDepthOrderbookEngine(max_depth=20)
        step = max(float(atr) * 0.18, float(price) * 0.0005, 1e-8)
        bids = [(price - step * index, 1000 / index) for index in range(1, 13)]
        asks = [(price + step * index, 920 / index) for index in range(1, 13)]
        engine.apply_snapshot(bids=bids, asks=asks, sequence_id=sequence_id)
        return engine

    def _ladder(self, bids: list[DepthLevel], asks: list[DepthLevel]) -> list[dict[str, Any]]:
        ladder = []
        for index in range(max(len(bids), len(asks))):
            bid = bids[index] if index < len(bids) else DepthLevel(0.0, 0.0)
            ask = asks[index] if index < len(asks) else DepthLevel(0.0, 0.0)
            total = bid.size + ask.size
            imbalance = 0.0 if total <= 0 else (bid.size - ask.size) / total
            ladder.append(
                {
                    "level": index + 1,
                    "bid_price": round(bid.price, 8),
                    "bid_size": round(bid.size, 8),
                    "ask_price": round(ask.price, 8),
                    "ask_size": round(ask.size, 8),
                    "imbalance": round(imbalance * 100, 2),
                    "intensity": round(min(total / max((bids[0].size + asks[0].size) if bids and asks else total, 1e-8), 1.0) * 100, 2),
                }
            )
        return ladder[: self.max_depth]

    @staticmethod
    def _spoofing_alerts(ladder: list[dict[str, Any]]) -> list[dict[str, Any]]:
        alerts = []
        for level in ladder[5:15]:
            if abs(float(level["imbalance"])) >= 78 and float(level["intensity"]) >= 55:
                alerts.append({"level": level["level"], "side": "BID" if level["imbalance"] > 0 else "ASK", "reason": "large off-touch imbalance"})
        return alerts[:4]

    @staticmethod
    def _iceberg_alerts(ladder: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {"level": level["level"], "side": "BID" if level["imbalance"] > 0 else "ASK", "reason": "persistent high intensity"}
            for level in ladder[:6]
            if abs(float(level["imbalance"])) <= 18 and float(level["intensity"]) >= 72
        ][:4]

    def _levels(self, source: dict[float, float], *, reverse: bool) -> list[DepthLevel]:
        return [
            DepthLevel(price, size)
            for price, size in sorted(source.items(), reverse=reverse)[: self.max_depth]
        ]

    def _normalize(self, levels: list[tuple[float, float]], *, reverse: bool) -> dict[float, float]:
        cleaned = {float(price): float(size) for price, size in levels if float(price) > 0 and float(size) > 0}
        ordered = sorted(cleaned.items(), reverse=reverse)[: self.max_depth]
        return dict(ordered)

    @staticmethod
    def _apply_updates(book: dict[float, float], updates: list[tuple[float, float]]) -> None:
        for price, size in updates:
            normalized_price = float(price)
            normalized_size = float(size)
            if normalized_size <= 0:
                book.pop(normalized_price, None)
            else:
                book[normalized_price] = normalized_size
