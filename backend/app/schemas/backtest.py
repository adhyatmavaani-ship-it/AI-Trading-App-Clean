from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class BacktestRequest(BaseModel):
    symbol: str
    timeframe: Literal["1m", "5m", "15m", "1h"] = "5m"
    strategy: Literal["ensemble", "hybrid_crypto", "ema_crossover", "rsi", "breakout"] = "ensemble"
    starting_balance: float = Field(default=10_000, gt=0)
    start_at: datetime
    end_at: datetime
    strategy_params: dict[str, int | float] = Field(default_factory=dict)
    risk_profile: Literal["low", "medium", "high"] = "medium"


class BacktestMetrics(BaseModel):
    pnl: float
    win_rate: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    profit_factor: float
    max_win_streak: int
    max_loss_streak: int
    total_return: float
    trades: int


class BacktestTrade(BaseModel):
    side: str
    entry: float
    exit: float
    profit: float
    confidence: float
    regime: str
    reason: str


class EquityPoint(BaseModel):
    step: int
    equity: float
    regime: str


class BacktestResponse(BaseModel):
    symbol: str
    metrics: BacktestMetrics
    trades: list[BacktestTrade]
    equity_curve: list[EquityPoint]
    strategy: str = "ensemble"
    strategy_params: dict[str, int | float] = Field(default_factory=dict)


class StrategyOptimizationRequest(BaseModel):
    symbol: str
    timeframe: Literal["1m", "5m", "15m", "1h"] = "5m"
    strategy: Literal["ema_crossover", "rsi"] = "ema_crossover"
    starting_balance: float = Field(default=10_000, gt=0)
    start_at: datetime
    end_at: datetime
    ema_fast_periods: list[int] = Field(default_factory=list)
    ema_slow_periods: list[int] = Field(default_factory=list)
    rsi_periods: list[int] = Field(default_factory=list)
    rsi_oversold_thresholds: list[float] = Field(default_factory=list)
    rsi_overbought_thresholds: list[float] = Field(default_factory=list)
    max_parallelism: int = Field(default=4, ge=1, le=16)
    use_cache: bool = True


class OptimizedStrategyResult(BaseModel):
    rank: int
    strategy: str
    parameters: dict[str, int | float]
    pnl: float
    max_drawdown: float
    win_rate: float
    trades: int
    score: float


class StrategyOptimizationResponse(BaseModel):
    symbol: str
    strategy: str
    best_parameters: dict[str, int | float]
    best_result: OptimizedStrategyResult
    rankings: list[OptimizedStrategyResult]
    total_runs: int
    cache_hit: bool = False
