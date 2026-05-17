from __future__ import annotations

import math
import random
from typing import Any


class QuantAnalyticsEngine:
    """Institutional diagnostics for closed trade/result streams."""

    def analyze(self, trades: list[dict[str, Any]], *, simulations: int = 250) -> dict[str, Any]:
        returns = [float(item.get("return_pct", item.get("pnl_pct", item.get("pnl", 0.0))) or 0.0) for item in trades]
        if not returns:
            return self._empty()
        wins = [value for value in returns if value > 0]
        losses = [value for value in returns if value < 0]
        expectancy = sum(returns) / len(returns)
        volatility = _std(returns)
        sharpe = 0.0 if volatility <= 0 else (expectancy / volatility) * math.sqrt(max(len(returns), 1))
        equity = []
        running = 0.0
        for value in returns:
            running += value
            equity.append(running)
        max_drawdown = self._max_drawdown(equity)
        monte_carlo = self._monte_carlo(returns, simulations=simulations)
        return {
            "trade_count": len(returns),
            "sharpe_ratio": round(sharpe, 4),
            "expectancy": round(expectancy, 6),
            "max_drawdown": round(max_drawdown, 6),
            "win_rate": round(len(wins) / len(returns) * 100, 2),
            "profit_factor": round(sum(wins) / max(abs(sum(losses)), 1e-8), 4),
            "volatility_clustering": round(self._volatility_clustering(returns), 4),
            "edge_persistence": round(self._edge_persistence(returns), 4),
            "strategy_decay_score": round(self._strategy_decay(returns), 4),
            "win_loss_clustering": self._cluster_lengths(returns),
            "monte_carlo": monte_carlo,
            "execution_efficiency": round(max(0.0, min(1.0, 1.0 - abs(max_drawdown))) * 100, 2),
        }

    @staticmethod
    def _empty() -> dict[str, Any]:
        return {
            "trade_count": 0,
            "sharpe_ratio": 0.0,
            "expectancy": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "volatility_clustering": 0.0,
            "edge_persistence": 0.0,
            "strategy_decay_score": 0.0,
            "win_loss_clustering": {"max_win_streak": 0, "max_loss_streak": 0},
            "monte_carlo": {"p05": 0.0, "p50": 0.0, "p95": 0.0},
            "execution_efficiency": 0.0,
        }

    @staticmethod
    def _max_drawdown(equity: list[float]) -> float:
        peak = equity[0]
        drawdown = 0.0
        for value in equity:
            peak = max(peak, value)
            drawdown = min(drawdown, value - peak)
        return drawdown

    @staticmethod
    def _volatility_clustering(returns: list[float]) -> float:
        if len(returns) < 4:
            return 0.0
        abs_returns = [abs(value) for value in returns]
        mean = sum(abs_returns) / len(abs_returns)
        clustered = sum(1 for left, right in zip(abs_returns, abs_returns[1:]) if left > mean and right > mean)
        return clustered / max(len(abs_returns) - 1, 1)

    @staticmethod
    def _edge_persistence(returns: list[float]) -> float:
        if len(returns) < 6:
            return 0.0
        midpoint = len(returns) // 2
        early = sum(returns[:midpoint]) / max(midpoint, 1)
        late = sum(returns[midpoint:]) / max(len(returns) - midpoint, 1)
        return 1.0 if early == 0 else max(-1.0, min(1.0, late / abs(early)))

    @staticmethod
    def _strategy_decay(returns: list[float]) -> float:
        if len(returns) < 6:
            return 0.0
        third = max(len(returns) // 3, 1)
        recent = sum(returns[-third:]) / third
        baseline = sum(returns[:-third]) / max(len(returns) - third, 1)
        return max(0.0, min(1.0, (baseline - recent) / max(abs(baseline), 1e-8)))

    @staticmethod
    def _cluster_lengths(returns: list[float]) -> dict[str, int]:
        max_win = max_loss = current_win = current_loss = 0
        for value in returns:
            if value > 0:
                current_win += 1
                current_loss = 0
            elif value < 0:
                current_loss += 1
                current_win = 0
            else:
                current_win = current_loss = 0
            max_win = max(max_win, current_win)
            max_loss = max(max_loss, current_loss)
        return {"max_win_streak": max_win, "max_loss_streak": max_loss}

    @staticmethod
    def _monte_carlo(returns: list[float], *, simulations: int) -> dict[str, float]:
        rng = random.Random(1337)
        outcomes = []
        for _ in range(max(10, min(simulations, 2000))):
            sample = [rng.choice(returns) for _ in returns]
            outcomes.append(sum(sample))
        outcomes.sort()
        return {
            "p05": round(outcomes[int(len(outcomes) * 0.05)], 6),
            "p50": round(outcomes[int(len(outcomes) * 0.50)], 6),
            "p95": round(outcomes[int(len(outcomes) * 0.95) - 1], 6),
        }


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))
