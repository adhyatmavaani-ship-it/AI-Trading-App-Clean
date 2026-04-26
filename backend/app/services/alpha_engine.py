from __future__ import annotations

from dataclasses import dataclass

from app.schemas.trading import AlphaContext, AIInference, FeatureSnapshot


@dataclass
class AlphaEngine:
    """Combines heterogeneous alpha sources into one institutional decision score."""

    def score(
        self,
        snapshot: FeatureSnapshot,
        inference: AIInference,
        alpha: AlphaContext,
        weight_context: dict | None = None,
        execution_costs: dict | None = None,
    ) -> dict:
        base_weights = {
            "ai": 0.38,
            "whale": 0.18,
            "sentiment": 0.14,
            "liquidity": 0.16,
            "regime": 0.14,
        }
        weights = self._dynamic_weights(base_weights, weight_context or {})

        ai_component = inference.confidence_score
        whale_component = alpha.whale.score
        sentiment_component = min(1.0, alpha.sentiment.hype_score / 1.5)
        liquidity_component = max(0.0, 1 - alpha.liquidity.rug_pull_risk)
        regime_component = self._regime_component(snapshot.regime)

        final_score = (
            ai_component * weights["ai"]
            + whale_component * weights["whale"]
            + sentiment_component * weights["sentiment"]
            + liquidity_component * weights["liquidity"]
            + regime_component * weights["regime"]
        )
        expected_return = (
            inference.expected_return * 0.65
            + alpha.whale.accumulation_score * 0.015
            + alpha.sentiment.buzz_score * 0.01
        )
        execution_costs = execution_costs or {}
        gas_fee = float(execution_costs.get("gas_fee", 0.0))
        priority_fee = float(execution_costs.get("priority_fee_cost", 0.0))
        mev_tip = float(execution_costs.get("mev_tip", 0.0))
        total_cost = gas_fee + priority_fee + mev_tip
        net_expected_return = expected_return - total_cost
        risk_score = min(
            1.0,
            inference.expected_risk * 0.45
            + alpha.liquidity.rug_pull_risk * 0.30
            + alpha.security.honeypot_risk * 0.15
            + alpha.security.blacklist_risk * 0.10,
        )
        min_net_profit = float(weight_context.get("min_net_profit_threshold", 0.001)) if weight_context else 0.001
        allow_trade = final_score > 0.60 and net_expected_return > max(risk_score * 0.01, min_net_profit)
        return {
            "weights": weights,
            "final_score": round(final_score * 100, 2),
            "final_score_normalized": final_score,
            "expected_return": expected_return,
            "net_expected_return": net_expected_return,
            "profit_margin_over_cost": net_expected_return - total_cost,
            "risk_score": risk_score,
            "execution_cost_total": total_cost,
            "execution_costs": {
                "gas_fee": gas_fee,
                "priority_fee_cost": priority_fee,
                "mev_tip": mev_tip,
                "total_cost": total_cost,
            },
            "allow_trade": allow_trade,
        }

    def _dynamic_weights(self, base_weights: dict[str, float], weight_context: dict) -> dict[str, float]:
        adjusted = dict(base_weights)
        source_metrics = weight_context.get("source_metrics", {})
        for source, metrics in source_metrics.items():
            if source not in adjusted:
                continue
            win_rate = float(metrics.get("win_rate", 0.5))
            profit_factor = float(metrics.get("profit_factor", 1.0))
            drift = float(metrics.get("drift_penalty", 0.0))
            multiplier = max(0.6, min(1.4, (win_rate / 0.5) * min(1.2, profit_factor / 1.0) * (1 - drift)))
            adjusted[source] *= multiplier

        total = sum(adjusted.values()) or 1.0
        return {key: value / total for key, value in adjusted.items()}

    def _regime_component(self, regime: str) -> float:
        mapping = {
            "TRENDING": 0.75,
            "RANGING": 0.52,
            "VOLATILE": 0.48,
        }
        return mapping.get(regime, 0.50)
