from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WhaleTracker:
    """Scores cross-chain whale activity and turns it into actionable intelligence."""

    profitable_wallets: dict[str, list[dict]]

    @classmethod
    def create_default(cls) -> "WhaleTracker":
        seeded = {
            "ethereum": [{"wallet": f"eth_whale_{idx}", "win_rate": 0.55 + idx * 0.001, "roi": 0.20, "consistency": 0.70} for idx in range(34)],
            "solana": [{"wallet": f"sol_whale_{idx}", "win_rate": 0.58 + idx * 0.001, "roi": 0.25, "consistency": 0.66} for idx in range(33)],
            "base": [{"wallet": f"base_whale_{idx}", "win_rate": 0.57 + idx * 0.001, "roi": 0.22, "consistency": 0.68} for idx in range(33)],
        }
        return cls(profitable_wallets=seeded)

    async def evaluate_token(self, symbol: str, chain: str, market_features: dict[str, float]) -> dict:
        wallets = self.profitable_wallets.get(chain.lower(), [])[:100]
        wallet_count = len(wallets)
        imbalance = abs(market_features.get("order_book_imbalance", 0.0))
        accumulation_score = min(1.0, 0.45 + imbalance + market_features.get("15m_volume", 0.0) / 1_000_000)
        unusual_activity_score = min(1.0, market_features.get("volatility", 0.0) * 10 + market_features.get("1m_return", 0.0) * 15)
        new_token_entry = accumulation_score > 0.75 and unusual_activity_score > 0.45
        score = min(1.0, accumulation_score * 0.55 + unusual_activity_score * 0.25 + wallet_count / 1000)
        return {
            "chain": chain,
            "wallet_count": wallet_count,
            "score": score,
            "accumulation_score": accumulation_score,
            "unusual_activity_score": unusual_activity_score,
            "new_token_entry": new_token_entry,
            "summary": f"{chain} smart money score {score:.2f} with {wallet_count} tracked wallets on {symbol}",
            "top_wallets": wallets[:5],
        }

    def wallet_scorecard(self, chain: str) -> list[dict]:
        wallets = self.profitable_wallets.get(chain.lower(), [])
        scored = []
        for wallet in wallets[:100]:
            score = wallet["win_rate"] * 0.4 + wallet["roi"] * 0.35 + wallet["consistency"] * 0.25
            scored.append({**wallet, "score": round(score, 4)})
        return sorted(scored, key=lambda item: item["score"], reverse=True)
