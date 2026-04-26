from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app.schemas.trading import AIInference, FeatureSnapshot
from app.services.trade_probability import TradeProbabilityEngine
from app.trading.strategies.base import StrategyDecision
from app.trading.strategies.engine import TradingStrategyEngine


@dataclass
class StrategyEngine:
    engine: TradingStrategyEngine = field(default_factory=TradingStrategyEngine)
    probability_engine: TradeProbabilityEngine | None = None

    def analyze_all(
        self,
        frame: pd.DataFrame | dict[str, pd.DataFrame],
        snapshot: FeatureSnapshot | None = None,
        strategy_params: dict[str, int | float] | dict[str, dict[str, int | float]] | None = None,
    ) -> list[StrategyDecision]:
        decisions = self.engine.evaluate_all(frame, strategy_params=strategy_params)
        if self.probability_engine is None:
            return decisions
        return [
            self.probability_engine.enrich_decision(
                decision,
                snapshot=snapshot,
                frame=frame,
            )
            for decision in decisions
        ]

    def analyze(
        self,
        frame: pd.DataFrame | dict[str, pd.DataFrame],
        preferred_strategy: str = "ensemble",
        snapshot: FeatureSnapshot | None = None,
        strategy_params: dict[str, int | float] | dict[str, dict[str, int | float]] | None = None,
    ) -> StrategyDecision:
        decisions = self.analyze_all(frame, snapshot=snapshot, strategy_params=strategy_params)
        if preferred_strategy != "ensemble":
            for decision in decisions:
                if decision.strategy == preferred_strategy:
                    return decision
        actionable = [decision for decision in decisions if decision.signal != "HOLD"]
        if actionable:
            return max(actionable, key=lambda item: item.confidence)
        if snapshot is not None:
            return self._fallback_candidate(snapshot=snapshot, decisions=decisions)
        return max(decisions, key=lambda item: item.confidence, default=StrategyDecision("none", "HOLD", 0.0))

    def select(
        self,
        snapshot: FeatureSnapshot,
        inference: AIInference,
        frame: pd.DataFrame | dict[str, pd.DataFrame] | None = None,
    ) -> str:
        if isinstance(frame, dict):
            strategy_decision = self.analyze(frame)
            if strategy_decision.signal != "HOLD":
                return self._strategy_label(strategy_decision.strategy)
        elif frame is not None and not frame.empty:
            strategy_decision = self.analyze(frame)
            if strategy_decision.signal != "HOLD":
                return self._strategy_label(strategy_decision.strategy)
        if inference.decision == "HOLD":
            return "NO_TRADE"
        if snapshot.regime == "TRENDING":
            return "TREND_FOLLOW"
        if snapshot.regime == "RANGING":
            return "MEAN_REVERSION"
        if snapshot.regime == "VOLATILE":
            return "BREAKOUT"
        return "NO_TRADE"

    def _strategy_label(self, strategy_name: str) -> str:
        mapping = {
            "hybrid_crypto": "HYBRID_TREND_PULLBACK",
            "ema_crossover": "EMA_CROSSOVER",
            "rsi": "RSI_REVERSION",
            "breakout": "BREAKOUT",
        }
        return mapping.get(strategy_name, strategy_name.upper())

    def _fallback_candidate(
        self,
        *,
        snapshot: FeatureSnapshot,
        decisions: list[StrategyDecision],
    ) -> StrategyDecision:
        ema_spread = float(snapshot.features.get("15m_ema_spread", snapshot.features.get("5m_ema_spread", 0.0)))
        rsi = float(snapshot.features.get("5m_rsi", snapshot.features.get("15m_rsi", 50.0)))
        breakout_strength = abs(float(snapshot.features.get("15m_return", snapshot.features.get("5m_return", 0.0))))
        imbalance = float(snapshot.order_book_imbalance)
        signal = "BUY" if (ema_spread >= 0 and (rsi <= 68 or imbalance >= 0)) else "SELL"
        confidence = max(
            0.31,
            min(
                0.45,
                0.30 + min(abs(ema_spread) * 20, 0.08) + min(breakout_strength * 6, 0.05) + min(abs(imbalance) * 0.08, 0.04),
            ),
        )
        regime_type = str(snapshot.regime or "RANGING").upper()
        reason = ",".join(
            sorted(
                {
                    str(decision.metadata.get("reason", "hold"))
                    for decision in decisions
                    if str(decision.metadata.get("reason", "")).strip()
                }
            )
        ) or "all_strategies_hold"
        return StrategyDecision(
            strategy="fallback_watchlist",
            signal=signal,
            confidence=confidence,
            metadata={
                "reason": reason,
                "regime_type": regime_type,
                "adjusted_confidence": round(confidence, 6),
                "trade_success_probability": round(confidence, 6),
                "raw_trade_success_probability": round(confidence, 6),
                "fallback_candidate": "true",
            },
        )
