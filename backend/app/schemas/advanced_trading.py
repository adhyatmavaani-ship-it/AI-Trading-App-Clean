from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


WorkspaceMode = Literal["AI_MODE", "SCOUT_MODE", "EXECUTION_MODE"]
ChartOrderSide = Literal["BUY", "SELL"]
ChartOrderStatus = Literal["DRAFT", "STAGED", "ACTIVE", "CANCELLED"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_chart_order_id() -> str:
    return f"chart_{uuid4().hex}"


class EncryptApiKeyRequest(BaseModel):
    provider: str = Field(..., min_length=2, max_length=64)
    label: str = Field(..., min_length=1, max_length=80)
    raw_api_key: str = Field(..., min_length=8, max_length=4096)

    @field_validator("provider", "label")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()


class EncryptedApiKeyResponse(BaseModel):
    provider: str
    label: str
    key_hash: str
    encrypted_key: str
    encryption_iv: str
    encryption_tag: str
    key_preview: str


class AiStrategyContextRequest(BaseModel):
    slug: str = Field(..., min_length=2, max_length=80)
    version: str = Field(default="1", min_length=1, max_length=32)
    display_name: str = Field(..., min_length=2, max_length=120)
    model_family: str = Field(default="ml_signal", max_length=80)
    metrics: dict[str, Any] = Field(default_factory=dict)
    risk_context: dict[str, Any] = Field(default_factory=dict)
    signal_context: dict[str, Any] = Field(default_factory=dict)

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str) -> str:
        return value.strip().lower().replace(" ", "-")

    @field_validator("version")
    @classmethod
    def normalize_version(cls, value: str) -> str:
        return value.strip()


class AiStrategyContextResponse(BaseModel):
    ai_strategy_id: str
    slug: str
    version: str
    display_name: str
    model_family: str
    metrics: dict[str, Any]
    risk_context: dict[str, Any]
    signal_context: dict[str, Any]
    last_signal_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ChartOrderSyncRequest(BaseModel):
    chart_order_id: str | None = Field(default=None, max_length=80)
    ai_strategy_id: str | None = Field(default=None, max_length=80)
    workspace_mode: WorkspaceMode = "SCOUT_MODE"
    symbol: str = Field(..., min_length=2, max_length=32)
    exchange: str = Field(default="BINANCE", min_length=2, max_length=32)
    side: ChartOrderSide
    order_type: Literal["LIMIT", "STOP_LOSS", "TAKE_PROFIT"] = "LIMIT"
    limit_price: float | None = Field(default=None, gt=0)
    stop_loss: float | None = Field(default=None, gt=0)
    take_profit: float | None = Field(default=None, gt=0)
    quantity: float | None = Field(default=None, gt=0)
    is_ai_trailing: bool = False
    status: ChartOrderStatus = "DRAFT"
    client_revision: int = Field(default=1, ge=1)
    chart_context: dict[str, Any] = Field(default_factory=dict)

    @field_validator("symbol", "exchange")
    @classmethod
    def normalize_market_text(cls, value: str) -> str:
        return value.strip().upper()


class ChartOrderSyncResponse(BaseModel):
    chart_order_id: str
    user_id: str
    ai_strategy_id: str | None = None
    workspace_mode: WorkspaceMode
    symbol: str
    exchange: str
    side: ChartOrderSide
    order_type: str
    limit_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    quantity: float | None = None
    is_ai_trailing: bool
    status: ChartOrderStatus
    client_revision: int
    chart_context: dict[str, Any]
    created_at: datetime
    last_updated: datetime
