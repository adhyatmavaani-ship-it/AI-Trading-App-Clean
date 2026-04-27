from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings


@dataclass
class PortfolioManager:
    settings: Settings

    def compute_allocation(
        self,
        *,
        confidence: float,
        regime: str,
        symbol_score: float,
        drawdown_pct: float,
    ) -> float:
        risk_fraction = float(self.settings.portfolio_base_risk_per_trade)
        normalized_regime = str(regime or "RANGING").upper()

        if normalized_regime == "TRENDING":
            risk_fraction *= float(self.settings.portfolio_trending_risk_multiplier)
        elif normalized_regime == "HIGH_VOL":
            risk_fraction *= float(self.settings.portfolio_high_vol_risk_multiplier)
        elif normalized_regime == "LOW_VOL":
            risk_fraction *= float(self.settings.portfolio_low_vol_risk_multiplier)

        if float(symbol_score) > float(self.settings.portfolio_symbol_score_boost_threshold):
            risk_fraction *= float(self.settings.portfolio_symbol_score_boost_multiplier)

        if float(confidence) > float(self.settings.portfolio_confidence_risk_boost_threshold):
            risk_fraction *= float(self.settings.portfolio_confidence_risk_boost_multiplier)

        if float(drawdown_pct) > float(self.settings.portfolio_drawdown_hard_threshold):
            risk_fraction *= float(self.settings.portfolio_drawdown_hard_multiplier)
        elif float(drawdown_pct) > float(self.settings.portfolio_drawdown_soft_threshold):
            risk_fraction *= float(self.settings.portfolio_drawdown_soft_multiplier)

        return min(float(self.settings.portfolio_max_risk_per_trade), max(risk_fraction, 0.0))

    def assess_new_trade(
        self,
        *,
        active_trades: list[dict],
        symbol: str,
        side: str,
        proposed_risk_fraction: float,
        gross_exposure_pct: float,
        correlation_to_portfolio: float,
    ) -> dict:
        normalized_symbol = str(symbol or "").upper().strip()
        normalized_side = str(side or "").upper().strip()
        current_risk = self._active_risk_exposure(active_trades)
        correlated_count = self._correlated_trade_count(active_trades, normalized_symbol, normalized_side)
        multiplier = 1.0
        reason = ""

        if current_risk + float(proposed_risk_fraction) >= float(self.settings.portfolio_max_total_risk):
            return {
                "allow_trade": False,
                "risk_fraction": proposed_risk_fraction,
                "multiplier": 0.0,
                "reason": "Portfolio risk exposure limit reached",
                "correlated_count": correlated_count,
                "correlation_risk": round(float(correlation_to_portfolio), 8),
            }

        if correlated_count >= int(self.settings.portfolio_max_correlated_trades):
            multiplier *= 0.7
            reason = "Correlated trade cluster detected"

        if float(correlation_to_portfolio) >= float(self.settings.portfolio_correlation_reduce_threshold):
            multiplier *= max(float(self.settings.portfolio_correlation_min_multiplier), 0.75)
            reason = reason or "High portfolio correlation"

        adjusted_risk = proposed_risk_fraction * multiplier
        remaining = max(0.0, float(self.settings.portfolio_max_total_risk) - current_risk)
        adjusted_risk = min(adjusted_risk, remaining)

        return {
            "allow_trade": adjusted_risk > 0.0,
            "risk_fraction": round(adjusted_risk, 8),
            "multiplier": round(multiplier, 8),
            "reason": reason,
            "correlated_count": correlated_count,
            "correlation_risk": round(float(correlation_to_portfolio), 8),
        }

    def summary(self, *, active_trades: list[dict], gross_exposure_pct: float) -> dict:
        return {
            "capital_utilization": round(
                min(1.0, float(gross_exposure_pct) / max(float(self.settings.max_portfolio_exposure_pct), 1e-8)),
                8,
            ),
            "risk_exposure": round(self._active_risk_exposure(active_trades), 8),
            "correlation_risk": round(self._average_correlation_risk(active_trades), 8),
        }

    def _active_risk_exposure(self, active_trades: list[dict]) -> float:
        return sum(float(trade.get("risk_fraction", 0.0) or 0.0) for trade in active_trades)

    def _average_correlation_risk(self, active_trades: list[dict]) -> float:
        if not active_trades:
            return 0.0
        values = [float(trade.get("portfolio_correlation_risk", 0.0) or 0.0) for trade in active_trades]
        return sum(values) / max(len(values), 1)

    def _correlated_trade_count(self, active_trades: list[dict], symbol: str, side: str) -> int:
        candidate_family = self._correlation_family(symbol)
        count = 0
        for trade in active_trades:
            trade_side = str(trade.get("side", "") or "").upper().strip()
            if trade_side != side:
                continue
            trade_family = self._correlation_family(str(trade.get("symbol", "") or "").upper())
            if trade_family == candidate_family:
                count += 1
        return count

    def _correlation_family(self, symbol: str) -> str:
        normalized = str(symbol or "").upper().strip()
        for suffix in ("USDT", "USDC", "USD", "BTC", "ETH"):
            if normalized.endswith(suffix) and len(normalized) > len(suffix):
                normalized = normalized[: -len(suffix)]
                break
        majors = {"BTC", "ETH", "SOL", "AVAX", "ADA", "XRP", "DOT", "ATOM", "NEAR"}
        return "MAJORS" if normalized in majors else normalized
