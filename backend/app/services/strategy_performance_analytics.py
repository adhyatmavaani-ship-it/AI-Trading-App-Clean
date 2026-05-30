from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class StrategyPerformanceAnalyticsProcessor:
    """Replay-safe analytics for advisory chart/mock actions.

    The processor reads mock/testnet action records and produces UI metrics only.
    It does not call broker, risk, execution, or strategy-selection services.
    """

    def snapshot(self, *, user_id: str, actions: list[dict[str, Any]]) -> dict[str, Any]:
        ordered = sorted(actions, key=lambda item: str(item.get("created_at") or ""))
        normalized = [self._normalize_action(action) for action in ordered]
        if not normalized:
            return self._empty_snapshot(user_id)

        accepted = [item for item in normalized if item["accepted"]]
        rejected = [item for item in normalized if not item["accepted"]]
        prices = [item["price"] for item in normalized if item["price"] > 0]
        returns = self._returns(prices)
        win_count = sum(1 for value in returns if value > 0)
        loss_count = sum(1 for value in returns if value < 0)
        total_outcomes = max(win_count + loss_count, 1)
        average_return = sum(returns) / max(len(returns), 1)
        volatility = self._population_stddev(returns)
        sharpe = 0.0 if volatility <= 0 else (average_return / volatility) * math.sqrt(max(len(returns), 1))
        time_decay = self._time_decay_risk(normalized)
        slippage_pressure = self._slippage_pressure(normalized, volatility)

        return {
            "event": "strategy_performance_update",
            "timestamp": _now_iso(),
            "user_id": user_id,
            "advisory_only": True,
            "simulation_only": True,
            "live_broker_submission": False,
            "rolling_window": len(normalized),
            "action_count": len(normalized),
            "accepted_count": len(accepted),
            "rejected_count": len(rejected),
            "win_loss_ratio": round(win_count / total_outcomes, 6),
            "loss_ratio": round(loss_count / total_outcomes, 6),
            "sharpe_estimate": round(sharpe, 6),
            "time_decay_risk": round(time_decay, 6),
            "slippage_pressure": round(slippage_pressure, 6),
            "ai_trailing_ratio": round(
                sum(1 for item in normalized if item["is_ai_trailing"]) / max(len(normalized), 1),
                6,
            ),
            "symbol_breakdown": self._symbol_breakdown(normalized),
            "stress_simulation": self._stress_simulation(normalized, returns, volatility),
        }

    @staticmethod
    def _normalize_action(action: dict[str, Any]) -> dict[str, Any]:
        payload = dict(action.get("action_payload") or {})
        accepted = payload.get("accepted")
        return {
            "action_id": str(action.get("action_id") or ""),
            "symbol": str(action.get("symbol") or "").upper(),
            "side": str(action.get("side") or "").upper(),
            "price": float(action.get("price") or 0.0),
            "quantity": float(action.get("quantity") or 0.0),
            "is_ai_trailing": bool(action.get("is_ai_trailing")),
            "created_at": str(action.get("created_at") or ""),
            "accepted": accepted is not False,
        }

    @staticmethod
    def _returns(prices: list[float]) -> list[float]:
        returns: list[float] = []
        for previous, current in zip(prices, prices[1:]):
            if previous > 0:
                returns.append((current - previous) / previous)
        return returns

    @staticmethod
    def _population_stddev(values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        return math.sqrt(max(variance, 0.0))

    @staticmethod
    def _time_decay_risk(actions: list[dict[str, Any]]) -> float:
        if not actions:
            return 0.0
        trailing_bonus = sum(1 for item in actions if item["is_ai_trailing"]) / len(actions)
        rejection_pressure = sum(1 for item in actions if not item["accepted"]) / len(actions)
        stale_pressure = min(len(actions), 50) / 50
        return max(0.0, min(1.0, (stale_pressure * 0.35) + (rejection_pressure * 0.45) - (trailing_bonus * 0.20)))

    @staticmethod
    def _slippage_pressure(actions: list[dict[str, Any]], volatility: float) -> float:
        if not actions:
            return 0.0
        notional_values = [item["price"] * item["quantity"] for item in actions if item["price"] > 0 and item["quantity"] > 0]
        avg_notional = sum(notional_values) / max(len(notional_values), 1)
        size_pressure = min(avg_notional / 100000.0, 1.0)
        return max(0.0, min(1.0, (volatility * 25.0) + (size_pressure * 0.35)))

    @staticmethod
    def _symbol_breakdown(actions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        breakdown: dict[str, dict[str, Any]] = {}
        for action in actions:
            symbol = action["symbol"] or "UNKNOWN"
            bucket = breakdown.setdefault(
                symbol,
                {"actions": 0, "accepted": 0, "ai_trailing": 0, "last_price": 0.0},
            )
            bucket["actions"] += 1
            bucket["accepted"] += 1 if action["accepted"] else 0
            bucket["ai_trailing"] += 1 if action["is_ai_trailing"] else 0
            if action["price"] > 0:
                bucket["last_price"] = action["price"]
        return breakdown

    @staticmethod
    def _stress_simulation(actions: list[dict[str, Any]], returns: list[float], volatility: float) -> dict[str, Any]:
        exposure = sum(item["price"] * item["quantity"] for item in actions if item["price"] > 0 and item["quantity"] > 0)
        flash_crash_loss = exposure * 0.12
        volatility_loss = exposure * min(0.20, volatility * 3.0)
        liquidity_gap_loss = exposure * min(0.08, 0.015 + len(actions) / 2000.0)
        worst_case = max(flash_crash_loss, volatility_loss, liquidity_gap_loss)
        return {
            "advisory_only": True,
            "simulation_only": True,
            "scenario_count": 3,
            "flash_crash_drawdown": round(flash_crash_loss, 6),
            "volatility_spike_drawdown": round(volatility_loss, 6),
            "liquidity_gap_drawdown": round(liquidity_gap_loss, 6),
            "worst_case_drawdown": round(worst_case, 6),
            "return_observations": len(returns),
        }

    @staticmethod
    def _empty_snapshot(user_id: str) -> dict[str, Any]:
        return {
            "event": "strategy_performance_update",
            "timestamp": _now_iso(),
            "user_id": user_id,
            "advisory_only": True,
            "simulation_only": True,
            "live_broker_submission": False,
            "rolling_window": 0,
            "action_count": 0,
            "accepted_count": 0,
            "rejected_count": 0,
            "win_loss_ratio": 0.0,
            "loss_ratio": 0.0,
            "sharpe_estimate": 0.0,
            "time_decay_risk": 0.0,
            "slippage_pressure": 0.0,
            "ai_trailing_ratio": 0.0,
            "symbol_breakdown": {},
            "stress_simulation": {
                "advisory_only": True,
                "simulation_only": True,
                "scenario_count": 0,
                "worst_case_drawdown": 0.0,
                "return_observations": 0,
            },
        }
