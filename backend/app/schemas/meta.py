from typing import Any

from pydantic import BaseModel, Field


class MetaDecisionResponse(BaseModel):
    trade_id: str
    user_id: str
    symbol: str
    decision: str
    strategy: str
    confidence: float
    signals: dict[str, Any] = Field(default_factory=dict)
    conflicts: list[str] = Field(default_factory=list)
    risk_adjustments: dict[str, Any] = Field(default_factory=dict)
    system_health_snapshot: dict[str, Any] = Field(default_factory=dict)
    reason: str
    created_at: str | None = None
    outcome: dict[str, Any] | None = None


class MetaBlockedTradesStats(BaseModel):
    total: int = 0
    reasons: dict[str, int] = Field(default_factory=dict)


class MetaStrategyPerformanceItem(BaseModel):
    trades: int = 0
    wins: int = 0
    losses: int = 0
    blocked: int = 0
    pnl: float = 0.0


class MetaAnalyticsResponse(BaseModel):
    blocked_trades: MetaBlockedTradesStats = Field(default_factory=MetaBlockedTradesStats)
    strategy_performance: dict[str, MetaStrategyPerformanceItem] = Field(default_factory=dict)
    confidence_distribution: dict[str, int] = Field(default_factory=dict)
    signal_pipeline: dict[str, Any] = Field(default_factory=dict)
    updated_at: str | None = None
