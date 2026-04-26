from pydantic import BaseModel, Field


class SimulationRequest(BaseModel):
    trades: int = Field(default=1_000, ge=10, le=20_000)
    starting_balance: float = Field(default=10_000, gt=0)
    days: int = Field(default=14, ge=1, le=60)
    include_api_failures: bool = True
    include_duplicates: bool = True
    include_latency: bool = True
    include_crashes: bool = True


class SimulationSummary(BaseModel):
    trades_processed: int
    win_rate: float
    profit_factor: float
    max_drawdown: float
    daily_returns: list[float]
    duplicate_signals_blocked: int
    api_failures_handled: int
    no_crashes: bool
    risk_limit_breaches: int


class PerformanceReport(BaseModel):
    period_days: int
    win_rate: float
    profit_factor: float
    max_drawdown: float
    daily_returns: list[float]
    total_return: float
    trades: int
