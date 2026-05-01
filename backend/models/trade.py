from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class SignalPayload(BaseModel):
    strategy: str
    signal: Literal["BUY", "SELL"]
    symbol: str
    price: float = Field(gt=0)
    atr: float | None = Field(default=None, gt=0)
    capital: float | None = Field(default=None, gt=0)


class StrategyPerformance(BaseModel):
    strategy: str
    total_trades: int = 0
    win_rate: float = 0.0
    recent_win_rate: float = 0.0
    profit_factor: float = 0.0
    momentum: float = 0.0
    drawdown: float = 0.0
    score: float = 0.0
    confidence: float = 0.0
    disabled: bool = False


class MetaDecision(BaseModel):
    approved: bool
    selected_strategy: str | None = None
    score: float
    confidence: float = 0.0
    reason: str
    performance: list[StrategyPerformance] = Field(default_factory=list)


class RiskDecision(BaseModel):
    approved: bool
    reason: str
    risk_pct: float
    stop_loss: float
    take_profit: float
    atr: float
    daily_pnl: float
    consecutive_losses: int


class TradeRecord(BaseModel):
    trade_id: str = Field(default_factory=lambda: uuid4().hex)
    strategy: str
    signal: Literal["BUY", "SELL"]
    symbol: str
    entry_price: float
    stop_loss: float | None = None
    take_profit: float | None = None
    position_size: float | None = None
    atr: float | None = None
    confidence: float | None = None
    exit_price: float | None = None
    price_source: str | None = None
    broker_order_id: str | None = None
    exchange_status: str | None = None
    filled_qty: float | None = None
    avg_fill_price: float | None = None
    pnl: float = 0.0
    approved_by_meta: bool = False
    approved_by_risk: bool = False
    status: Literal["rejected", "open", "closed"] = "open"
    rejection_reason: str | None = None
    close_reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    closed_at: datetime | None = None
    last_sync_at: datetime | None = None


class ExecutionResult(BaseModel):
    status: Literal["executed"]
    message: str
    trade: TradeRecord


class SignalResponse(BaseModel):
    status: Literal["executed", "rejected"]
    executed: bool
    selected_strategy: str | None = None
    confidence: float = 0.0
    meta: MetaDecision
    risk: RiskDecision | None = None
    execution: ExecutionResult | None = None
    trade: TradeRecord
