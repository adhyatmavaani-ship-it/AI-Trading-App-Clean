from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class SentimentEngine:
    """Builds narrative and hype scores from social activity proxies."""

    narratives: tuple[str, ...] = ("AI", "RWA", "memes", "DeFi", "gaming", "infrastructure")

    async def analyze_token(self, symbol: str, market_features: dict[str, float]) -> dict:
        buzz_score = min(1.0, abs(market_features.get("1m_return", 0.0)) * 12 + market_features.get("5m_volume", 0.0) / 2_000_000)
        real_volume = max(0.05, min(1.0, market_features.get("15m_volume", 0.0) / 2_500_000))
        hype_score = min(1.5, buzz_score / max(real_volume, 0.1))
        narrative_idx = int(abs(hash(symbol)) % len(self.narratives))
        narrative = self.narratives[narrative_idx]
        topic_clusters = [narrative, "smart-money" if market_features.get("order_book_imbalance", 0.0) > 0 else "distribution"]
        return {
            "buzz_score": buzz_score,
            "volume_alignment": real_volume,
            "hype_score": hype_score,
            "narrative": narrative,
            "topic_clusters": topic_clusters,
            "sentiment_vector": np.array([buzz_score, real_volume, hype_score]).tolist(),
        }
