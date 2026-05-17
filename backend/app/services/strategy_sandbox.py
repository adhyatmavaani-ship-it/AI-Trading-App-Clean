from __future__ import annotations

from typing import Any

from app.services.quant_analytics_engine import QuantAnalyticsEngine


class StrategySandbox:
    """Replay-driven strategy simulation facade with no live execution side effects."""

    def simulate(
        self,
        *,
        strategy_name: str,
        replay_events: list[dict[str, Any]],
        risk_fraction: float = 0.01,
    ) -> dict[str, Any]:
        trades = []
        open_price: float | None = None
        for event in replay_events:
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else event
            price = float(payload.get("close", payload.get("latest_price", 0.0)) or 0.0)
            signal = str(payload.get("signal", payload.get("decision", ""))).upper()
            if price <= 0:
                continue
            if open_price is None and signal in {"BUY", "LONG"}:
                open_price = price
            elif open_price is not None and signal in {"SELL", "EXIT"}:
                trades.append({"return_pct": ((price - open_price) / open_price) * float(risk_fraction)})
                open_price = None
        diagnostics = QuantAnalyticsEngine().analyze(trades)
        return {
            "strategy": strategy_name,
            "event_count": len(replay_events),
            "simulated_trades": len(trades),
            "diagnostics": diagnostics,
            "execution_mode": "SIMULATED_ONLY",
        }
