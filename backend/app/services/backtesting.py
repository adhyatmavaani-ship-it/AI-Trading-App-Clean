from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.core.config import Settings
from app.schemas.backtest import (
    BacktestRequest,
    BacktestResponse,
    StrategyOptimizationRequest,
    StrategyOptimizationResponse,
)
from app.services.market_data import MarketDataService
from app.services.risk_engine import RiskEngine
from app.services.strategy_engine import StrategyEngine
from app.trading.backtesting.engine import TradingBacktestingEngine
from app.trading.backtesting.optimizer import StrategyOptimizationEngine

if TYPE_CHECKING:
    from app.services.ai_engine import AIEngine
    from app.services.feature_pipeline import FeaturePipeline


@dataclass
class BacktestingEngine:
    settings: Settings
    market_data: MarketDataService
    feature_pipeline: FeaturePipeline
    ai_engine: AIEngine
    strategy_engine: StrategyEngine
    risk_engine: RiskEngine
    optimizer: StrategyOptimizationEngine | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.optimizer = StrategyOptimizationEngine(
            settings=self.settings,
            backtester=TradingBacktestingEngine(
                strategy_engine=self.strategy_engine.engine,
                risk_manager=self.risk_engine.manager,
                fee_rate=0.001,
                slippage_rate=0.001,
            ),
        )

    async def run(self, request: BacktestRequest) -> BacktestResponse:
        return await self.optimizer.backtester.run(request, self.market_data)

    async def optimize(self, request: StrategyOptimizationRequest) -> StrategyOptimizationResponse:
        return await self.optimizer.optimize(request, self.market_data)
