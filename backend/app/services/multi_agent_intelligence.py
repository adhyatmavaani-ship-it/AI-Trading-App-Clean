from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AgentVote:
    agent: str
    score: float
    direction: str
    weight: float
    reason: str


class MultiAgentIntelligenceEngine:
    """Small deterministic agent council for replay-safe AI reconstruction."""

    def evaluate(
        self,
        *,
        side: str,
        confidence: float,
        smc_confluence: float,
        liquidity_pressure: float,
        regime_confidence: float,
        trap_probability: float,
        momentum_score: float,
        risk_score: float,
    ) -> dict[str, Any]:
        normalized_side = "BUY" if str(side).upper() == "BUY" else "SELL"
        votes = [
            AgentVote("ScalperAgent", _clamp((confidence * 0.45) + (momentum_score * 0.55), 0.0, 1.0), normalized_side, 0.18, "short-term momentum and confidence"),
            AgentVote("StructureAgent", smc_confluence, normalized_side, 0.22, "SMC confluence"),
            AgentVote("LiquidityAgent", _clamp(liquidity_pressure * (1.0 - trap_probability), 0.0, 1.0), normalized_side, 0.18, "liquidity pressure after trap discount"),
            AgentVote("RegimeAgent", regime_confidence, normalized_side, 0.16, "market regime suitability"),
            AgentVote("RiskAgent", _clamp(1.0 - risk_score, 0.0, 1.0), normalized_side, 0.16, "risk acceptance"),
            AgentVote("MomentumAgent", momentum_score, normalized_side, 0.10, "momentum persistence"),
        ]
        weighted = sum(v.score * v.weight for v in votes) / max(sum(v.weight for v in votes), 1e-8)
        disagreement = _clamp(sum(abs(v.score - weighted) for v in votes) / len(votes), 0.0, 1.0)
        return {
            "consensus_score": round(weighted * 100, 2),
            "adaptive_confidence": round(_clamp(weighted - (disagreement * 0.18), 0.0, 1.0) * 100, 2),
            "disagreement_score": round(disagreement * 100, 2),
            "direction": normalized_side,
            "votes": [
                {
                    "agent": vote.agent,
                    "score": round(vote.score * 100, 2),
                    "direction": vote.direction,
                    "weight": vote.weight,
                    "reason": vote.reason,
                }
                for vote in votes
            ],
        }


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))
