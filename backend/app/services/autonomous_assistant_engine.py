from __future__ import annotations

from typing import Any


class AutonomousAssistantEngine:
    """Realtime-safe deterministic assistant reasoning for chart and replay."""

    def summarize(
        self,
        *,
        symbol: str,
        orderbook: dict[str, Any],
        orderflow: dict[str, Any],
        predictive: dict[str, Any],
        risk: dict[str, Any],
        regime: dict[str, Any],
    ) -> dict[str, Any]:
        warnings = list(risk.get("warnings") or [])
        trap = float(orderflow.get("trap_probability", 0.0) or 0.0)
        breakout = float(predictive.get("breakout_probability", 0.0) or 0.0)
        pressure = float(orderbook.get("pressure_score", 0.0) or 0.0)
        recommendations = []
        if warnings:
            recommendations.append("Reduce size or wait for cleaner execution conditions.")
        if trap >= 60:
            recommendations.append("Avoid chasing the first breakout candle; fakeout risk is elevated.")
        if breakout >= 65 and pressure >= 35:
            recommendations.append("Breakout path has supportive depth and orderflow pressure.")
        if not recommendations:
            recommendations.append("Wait for stronger liquidity, regime, or momentum confirmation.")
        return {
            "symbol": symbol.upper(),
            "mode": "ASSISTED",
            "summary": f"{symbol.upper()} regime is {str(regime.get('state', 'UNKNOWN')).lower()} with breakout probability {breakout:.1f}%.",
            "recommendations": recommendations,
            "voice_alert": self._voice_alert(warnings=warnings, trap=trap, breakout=breakout),
            "replay_safe": True,
        }

    @staticmethod
    def _voice_alert(*, warnings: list[dict[str, Any]], trap: float, breakout: float) -> str:
        if warnings:
            return "Risk warning. Execution conditions are degraded."
        if trap >= 60:
            return "Fakeout risk elevated. Wait for confirmation."
        if breakout >= 70:
            return "Breakout conditions improving."
        return "No high quality setup yet."
