from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

import pandas as pd


SignalType = Literal["BUY", "SELL", "HOLD"]


@dataclass(frozen=True)
class StrategyDecision:
    strategy: str
    signal: SignalType
    confidence: float
    metadata: dict[str, float | str] = field(default_factory=dict)


class BaseStrategy(ABC):
    name: str

    @abstractmethod
    def evaluate(
        self,
        data: pd.DataFrame | dict[str, pd.DataFrame],
        parameters: dict[str, int | float] | None = None,
    ) -> StrategyDecision:
        raise NotImplementedError

    def _hold(self, reason: str) -> StrategyDecision:
        return StrategyDecision(
            strategy=self.name,
            signal="HOLD",
            confidence=0.0,
            metadata={"reason": reason},
        )

    def _decision(
        self,
        signal: SignalType,
        confidence: float,
        **metadata: float | str,
    ) -> StrategyDecision:
        return StrategyDecision(
            strategy=self.name,
            signal=signal,
            confidence=max(0.0, min(float(confidence), 1.0)),
            metadata=metadata,
        )
