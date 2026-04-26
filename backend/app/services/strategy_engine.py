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

    def analyze(
        self,
        frame: pd.DataFrame | dict[str, pd.DataFrame],
        preferred_strategy: str = "ensemble",
        snapshot: FeatureSnapshot | None = None,
        strategy_params: dict[str, int | float] | dict[str, dict[str, int | float]] | None = None,
    ) -> StrategyDecision:
        decision = self.engine.evaluate(
            frame,
            preferred_strategy=preferred_strategy,
            strategy_params=strategy_params,
        )
        if self.probability_engine is None:
            return decision
        return self.probability_engine.enrich_decision(
            decision,
            snapshot=snapshot,
            frame=frame,
        )

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
