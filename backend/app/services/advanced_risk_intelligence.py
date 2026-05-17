from __future__ import annotations

from typing import Any


class AdvancedRiskIntelligence:
    """Advisory risk overlay; execution risk checks remain the source of truth."""

    def evaluate(
        self,
        *,
        volatility: float,
        spread_bps: float,
        trap_probability: float,
        liquidity_pressure: float,
        confidence: float,
        regime: str,
    ) -> dict[str, Any]:
        warnings: list[dict[str, Any]] = []
        if volatility >= 0.035:
            warnings.append({"code": "abnormal_volatility", "severity": "high", "message": "Volatility lock candidate"})
        if spread_bps >= 18:
            warnings.append({"code": "spread_explosion", "severity": "high", "message": "Spread is too wide for clean execution"})
        if trap_probability >= 0.62:
            warnings.append({"code": "liquidity_trap", "severity": "medium", "message": "Trap probability is elevated"})
        if liquidity_pressure <= 0.20:
            warnings.append({"code": "thin_liquidity", "severity": "medium", "message": "Liquidity pressure is weak"})
        regime_multiplier = 0.70 if str(regime).upper() in {"COMPRESSION", "MANIPULATION", "DISTRIBUTION"} else 1.0
        confidence_multiplier = max(0.25, min(float(confidence), 1.0))
        trap_multiplier = max(0.35, 1.0 - float(trap_probability) * 0.55)
        dynamic_size_multiplier = max(0.10, min(regime_multiplier * confidence_multiplier * trap_multiplier, 1.0))
        return {
            "dynamic_size_multiplier": round(dynamic_size_multiplier, 4),
            "risk_state": "BLOCK_CANDIDATE" if any(item["severity"] == "high" for item in warnings) else "NORMAL",
            "cooldown_seconds": 120 if warnings else 0,
            "warnings": warnings,
            "execution_note": "Advisory only. Final order routing still requires existing risk engine approval.",
        }
