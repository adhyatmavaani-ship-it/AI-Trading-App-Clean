from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LiquidityMonitor:
    """Monitors DEX liquidity stability and flags rug-pull style deterioration."""

    async def assess_token(self, symbol: str, chain: str, market_features: dict[str, float]) -> dict:
        liquidity_stability = max(0.0, 1 - min(0.9, market_features.get("volatility", 0.0) * 4))
        ownership_concentration = min(1.0, 0.25 + abs(market_features.get("order_book_imbalance", 0.0)))
        liquidity_removed = liquidity_stability < 0.35
        lp_burn_detected = market_features.get("5m_volume", 0.0) > market_features.get("15m_volume", 0.0) * 1.7
        rug_pull_risk = min(
            1.0,
            (1 - liquidity_stability) * 0.5
            + ownership_concentration * 0.35
            + (0.15 if liquidity_removed else 0.0)
            + (0.1 if lp_burn_detected else 0.0),
        )
        return {
            "chain": chain,
            "liquidity_stability": liquidity_stability,
            "ownership_concentration": ownership_concentration,
            "liquidity_removed": liquidity_removed,
            "lp_burn_detected": lp_burn_detected,
            "rug_pull_risk": rug_pull_risk,
        }
