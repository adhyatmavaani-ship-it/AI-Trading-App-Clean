from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class TaxEngine:
    """Tracks trade tax estimates and tax-loss harvesting candidates."""

    def estimate_trade_tax(self, profit: float, holding_period_days: int = 0) -> dict:
        tax_rate = 0.15 if holding_period_days >= 365 else 0.30
        estimated_tax = max(0.0, profit) * tax_rate
        return {
            "estimated_tax": estimated_tax,
            "lot_method": "FIFO",
            "tax_loss_harvest_candidate": profit < 0,
        }

    def export_yearly_report(self, user_id: str, trades: list[dict]) -> dict:
        realized_pnl = sum(float(trade.get("profit", 0.0) or 0.0) for trade in trades)
        taxes = sum(float(trade.get("estimated_tax", 0.0) or 0.0) for trade in trades)
        return {
            "user_id": user_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "trades": len(trades),
            "realized_pnl": realized_pnl,
            "estimated_tax_due": taxes,
            "tax_loss_harvest_candidates": [trade["trade_id"] for trade in trades if trade.get("profit", 0.0) < 0],
        }

