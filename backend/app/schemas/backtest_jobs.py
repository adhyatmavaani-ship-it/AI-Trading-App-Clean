from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AsyncBacktestRunRequest(BaseModel):
    symbol: str
    timeframe: Literal["1m", "5m", "15m", "1h"] = "5m"
    strategy: Literal["ensemble", "hybrid_crypto", "ema_crossover", "rsi", "breakout"] = "ensemble"
    starting_balance: float = Field(default=10_000, gt=0)
    days: int = Field(default=7, ge=1, le=30)
    risk_profile: Literal["low", "medium", "high"] = "medium"


class AsyncBacktestCompareRequest(BaseModel):
    symbol: str
    timeframe: Literal["1m", "5m", "15m", "1h"] = "5m"
    strategy: Literal["ensemble", "hybrid_crypto", "ema_crossover", "rsi", "breakout"] = "ensemble"
    starting_balance: float = Field(default=10_000, gt=0)
    days: int = Field(default=7, ge=1, le=30)
    profiles: list[Literal["low", "medium", "high"]] = Field(default_factory=lambda: ["low", "high"])


class BacktestJobLog(BaseModel):
    timestamp: datetime
    message: str


class BacktestJobSummary(BaseModel):
    symbol: str
    timeframe: str
    strategy: str
    days: int
    starting_balance: float
    final_equity: float
    total_profit: float
    roi_pct: float
    win_rate: float
    max_drawdown: float
    profit_factor: float
    total_trades: int


class BacktestEquityPoint(BaseModel):
    step: int
    equity: float
    regime: str = "UNKNOWN"


class BacktestJobResult(BaseModel):
    summary: BacktestJobSummary
    equity_curve: list[BacktestEquityPoint] = Field(default_factory=list)
    trades: list[dict] = Field(default_factory=list)


class BacktestComparisonProfileResult(BaseModel):
    risk_profile: Literal["low", "medium", "high"]
    summary: BacktestJobSummary
    equity_curve: list[BacktestEquityPoint] = Field(default_factory=list)
    trades: list[dict] = Field(default_factory=list)


class BacktestJobStatusResponse(BaseModel):
    job_id: str
    user_id: str
    status: Literal["QUEUED", "RUNNING", "COMPLETED", "FAILED"]
    progress_pct: float = 0.0
    current_stage: str = "queued"
    trades_found: int = 0
    net_profit: float = 0.0
    heartbeat_at: datetime | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    logs: list[BacktestJobLog] = Field(default_factory=list)
    result: BacktestJobResult | None = None
    comparison_profiles: list[BacktestComparisonProfileResult] = Field(default_factory=list)
