from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings


@dataclass
class PortfolioIntelligenceService:
    settings: Settings

    def build(
        self,
        *,
        ledger_snapshot: dict,
        strategy_performance: dict | None = None,
    ) -> dict:
        gross_profit = float(ledger_snapshot.get("gross_profit", 0.0) or 0.0)
        gross_loss = float(ledger_snapshot.get("gross_loss", 0.0) or 0.0)
        profit_factor = gross_profit / max(gross_loss, 1e-8)
        drawdown = float(ledger_snapshot.get("rolling_drawdown", 0.0) or 0.0)
        concentration = self._concentration(ledger_snapshot)
        strategy_scores = self._strategy_scores(strategy_performance or {})
        return {
            "profit_factor": round(profit_factor, 4),
            "strategy_health_tag": "Healthy Strategy" if profit_factor > 1.5 else "Needs Improvement",
            "drawdown_alert": drawdown >= 0.05,
            "risk_profile_mode": "conservative" if drawdown >= 0.05 else "normal",
            "drawdown_explanation": self._drawdown_explanation(drawdown),
            "concentration_warning": concentration["warning"],
            "largest_position_symbol": concentration["symbol"],
            "largest_position_pct": concentration["pct"],
            "strategy_scores": strategy_scores,
            "strategy_score_summary": self._strategy_summary(strategy_scores),
        }

    def _concentration(self, snapshot: dict) -> dict:
        equity = max(float(snapshot.get("current_equity", 0.0) or 0.0), 1e-8)
        largest_symbol = ""
        largest_value = 0.0
        for position in snapshot.get("positions", []) or []:
            symbol = str(position.get("symbol", "") or "").upper()
            value = abs(float(position.get("market_value", 0.0) or 0.0))
            if value > largest_value:
                largest_symbol = symbol
                largest_value = value
        pct = largest_value / equity
        warning = (
            f"Over-Concentration Risk: {largest_symbol} is {pct * 100:.0f}% of capital. Diversify your capital."
            if largest_symbol and pct >= 0.50
            else ""
        )
        return {"symbol": largest_symbol, "pct": round(pct, 4), "warning": warning}

    def _strategy_scores(self, raw: dict) -> dict[str, dict]:
        scores: dict[str, dict] = {}
        for name, payload in raw.items():
            if not isinstance(payload, dict):
                continue
            trades = int(payload.get("trades", 0) or 0)
            wins = int(payload.get("wins", 0) or 0)
            pnl = float(payload.get("pnl", 0.0) or 0.0)
            win_rate = wins / max(trades, 1)
            scores[str(name)] = {
                "trades": trades,
                "win_rate": round(win_rate, 4),
                "pnl": round(pnl, 4),
                "tag": "Working" if win_rate >= 0.55 and pnl >= 0 else "Losing Money" if pnl < 0 else "Needs More Data",
            }
        return scores

    def _strategy_summary(self, scores: dict[str, dict]) -> str:
        if not scores:
            return "Strategy-wise AI score will appear after enough closed trades."
        best_name, best = max(scores.items(), key=lambda item: (float(item[1].get("win_rate", 0.0)), float(item[1].get("pnl", 0.0))))
        losing = [
            f"{name} is losing money ({float(score.get('pnl', 0.0)):.2f})"
            for name, score in scores.items()
            if float(score.get("pnl", 0.0)) < 0
        ]
        base = f"Your {best_name} strategy has a {float(best.get('win_rate', 0.0)) * 100:.0f}% success rate."
        if losing:
            return f"{base} {losing[0]}."
        return base

    def _drawdown_explanation(self, drawdown: float) -> str:
        if drawdown >= 0.05:
            return "Drawdown crossed 5%; AI switched the risk profile to conservative mode."
        if drawdown > 0:
            return f"Portfolio is {drawdown * 100:.1f}% below peak capital."
        return "Portfolio is at or near peak capital."
