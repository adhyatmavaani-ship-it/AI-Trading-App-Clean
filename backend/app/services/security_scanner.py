from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SecurityScanner:
    """Performs token-level security checks before execution."""

    async def scan_token(self, symbol: str, chain: str, market_features: dict[str, float]) -> dict:
        volatility = market_features.get("volatility", 0.0)
        imbalance = abs(market_features.get("order_book_imbalance", 0.0))
        honeypot_risk = min(1.0, volatility * 6 + imbalance * 0.4)
        ownership_risk = min(1.0, 0.2 + volatility * 3)
        mint_risk = min(1.0, 0.15 + max(0.0, market_features.get("1m_return", 0.0)) * 15)
        blacklist_risk = min(1.0, 0.1 + max(0.0, -market_features.get("1m_return", 0.0)) * 20)
        tradable = honeypot_risk < 0.75 and blacklist_risk < 0.75
        notes = []
        if honeypot_risk >= 0.60:
            notes.append("Potential honeypot or blocked-sell behavior detected")
        if mint_risk >= 0.55:
            notes.append("Mint authority risk elevated")
        if ownership_risk >= 0.60:
            notes.append("Ownership privileges appear concentrated")
        return {
            "chain": chain,
            "honeypot_risk": honeypot_risk,
            "ownership_risk": ownership_risk,
            "mint_risk": mint_risk,
            "blacklist_risk": blacklist_risk,
            "tradable": tradable,
            "notes": notes,
        }
