from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app.trading.strategies.base import BaseStrategy, StrategyDecision
from app.trading.strategies.breakout import BreakoutStrategy
from app.trading.strategies.ema_crossover import EMACrossoverStrategy
from app.trading.strategies.hybrid_crypto import HybridCryptoStrategy
from app.trading.strategies.regime import MarketRegimeDetector
from app.trading.strategies.rsi_strategy import RSIStrategy


@dataclass
class TradingStrategyEngine:
    regime_detector: MarketRegimeDetector = field(default_factory=MarketRegimeDetector)
    strategies: list[BaseStrategy] = field(
        default_factory=lambda: [
            HybridCryptoStrategy(),
            EMACrossoverStrategy(),
            RSIStrategy(),
            BreakoutStrategy(),
        ]
    )

    def evaluate_all(
        self,
        data: pd.DataFrame | dict[str, pd.DataFrame],
        strategy_params: dict[str, int | float] | dict[str, dict[str, int | float]] | None = None,
    ) -> list[StrategyDecision]:
        if not isinstance(data, dict):
            return [
                strategy.evaluate(data, parameters=self._strategy_parameters(strategy.name, strategy_params))
                for strategy in self.strategies
            ]

        lower_frame = data.get("5m")
        if lower_frame is None:
            lower_frame = data.get("15m")
        if lower_frame is None:
            lower_frame = next(iter(data.values()))

        decisions: list[StrategyDecision] = []
        for strategy in self.strategies:
            strategy_input = data if strategy.name == "hybrid_crypto" else lower_frame
            decision = strategy.evaluate(
                strategy_input,
                parameters=self._strategy_parameters(strategy.name, strategy_params),
            )
            decision = self._apply_regime_overlay(decision, data if isinstance(data, dict) else lower_frame)
            decisions.append(decision)
        return decisions

    def evaluate(
        self,
        data: pd.DataFrame | dict[str, pd.DataFrame],
        preferred_strategy: str = "ensemble",
        strategy_params: dict[str, int | float] | dict[str, dict[str, int | float]] | None = None,
    ) -> StrategyDecision:
        decisions = self.evaluate_all(data, strategy_params=strategy_params)
        if preferred_strategy != "ensemble":
            for decision in decisions:
                if decision.strategy == preferred_strategy:
                    return decision
        actionable = [decision for decision in decisions if decision.signal != "HOLD"]
        if not actionable:
            return max(decisions, key=lambda item: item.confidence, default=StrategyDecision("none", "HOLD", 0.0))
        return max(actionable, key=lambda item: item.confidence)

    def _apply_regime_overlay(
        self,
        decision: StrategyDecision,
        data: pd.DataFrame | dict[str, pd.DataFrame],
    ) -> StrategyDecision:
        regime_frame = self._regime_frame(data)
        regime_state = self.regime_detector.detect(regime_frame)
        metadata = {
            **decision.metadata,
            "regime_type": regime_state.regime,
            "adx": round(regime_state.adx, 6),
            "atr": round(regime_state.atr, 8),
            "base_confidence": round(decision.confidence, 6),
        }
        if decision.strategy == "hybrid_crypto" and regime_state.regime != "TRENDING":
            metadata["adjusted_confidence"] = 0.0
            metadata["reason"] = "hybrid_requires_trending_regime"
            return StrategyDecision(
                strategy=decision.strategy,
                signal="HOLD",
                confidence=0.0,
                metadata=metadata,
            )

        adjusted_confidence = decision.confidence * regime_state.confidence_multiplier
        metadata["adjusted_confidence"] = round(adjusted_confidence, 6)
        return StrategyDecision(
            strategy=decision.strategy,
            signal=decision.signal,
            confidence=max(0.0, min(adjusted_confidence, 1.0)),
            metadata=metadata,
        )

    def _regime_frame(self, data: pd.DataFrame | dict[str, pd.DataFrame]) -> pd.DataFrame:
        if isinstance(data, dict):
            frame = data.get("1h")
            if frame is None:
                frame = data.get("15m")
            if frame is None:
                frame = next(iter(data.values()))
            return frame
        return data

    def _strategy_parameters(
        self,
        strategy_name: str,
        strategy_params: dict[str, int | float] | dict[str, dict[str, int | float]] | None,
    ) -> dict[str, int | float] | None:
        if not strategy_params:
            return None
        if all(isinstance(value, dict) for value in strategy_params.values()):
            nested = strategy_params.get(strategy_name, {})
            return dict(nested) if isinstance(nested, dict) else None
        return dict(strategy_params)
