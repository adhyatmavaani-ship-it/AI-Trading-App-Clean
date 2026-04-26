from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PublicPerformanceResponse(BaseModel):
    win_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    total_pnl_pct: float = 0.0
    total_trades: int = Field(default=0, ge=0)
    last_updated: datetime


class PublicTradeItem(BaseModel):
    symbol: str
    side: str
    entry: float
    exit: float
    pnl_pct: float
    status: Literal["WIN", "LOSS"]


class PublicTradesResponse(BaseModel):
    count: int = Field(default=0, ge=0)
    items: list[PublicTradeItem] = Field(default_factory=list)


class PublicDailyItem(BaseModel):
    date: str
    pnl_pct: float


class PublicDailyResponse(BaseModel):
    count: int = Field(default=0, ge=0)
    items: list[PublicDailyItem] = Field(default_factory=list)
