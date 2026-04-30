from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MarketCandlePayload(BaseModel):
    t: int
    o: float
    h: float
    l: float
    c: float
    v: float


class MarketStreamEnvelope(BaseModel):
    stream: str
    data: MarketCandlePayload


class MarketOhlcResponse(BaseModel):
    symbol: str
    interval: str
    stream: str
    candles: list[MarketCandlePayload]
    source: str
    educational_only: str = "Educational only. Not financial advice. No guaranteed profits."


class RiskEvaluationRequest(BaseModel):
    symbol: str = "BTCUSDT"
    side: Literal["long", "short"] = "long"
    account_equity: float = Field(gt=0)
    risk_amount: float = Field(gt=0)
    entry: float = Field(gt=0)
    stop_loss: float = Field(gt=0)
    take_profit: float = Field(gt=0)
    leverage: float = Field(default=1.0, ge=1.0, le=50.0)
    maker_fee_bps: float | None = Field(default=None, ge=0)
    taker_fee_bps: float | None = Field(default=None, ge=0)
    slippage_bps: float | None = Field(default=None, ge=0)
    confidence: float = Field(default=0.55, ge=0.0, le=1.0)
    reliability: float = Field(default=0.55, ge=0.0, le=1.0)
    liquidity_score: float = Field(default=0.7, ge=0.0, le=1.0)
    freshness_seconds: int = Field(default=15, ge=0)


class RiskEvaluationResponse(BaseModel):
    allowed: bool
    blockers: list[str]
    warnings: list[str]
    position_size: float
    quantity_step: float
    gross_risk_per_unit: float
    effective_risk_per_unit: float
    fee_per_unit: float
    slippage_per_unit: float
    risk_pct_of_equity: float
    notional: float
    leveraged_notional: float
    effective_rr: float
    expected_value: float
    heatmap_intensity: float
    heatmap_state: str
    educational_only: str = "Educational only. Not financial advice. No guaranteed profits."


class HeatmapZone(BaseModel):
    start_price: float
    end_price: float
    intensity: float
    state: Literal["neutral", "warning", "glow"]
    expected_value: float
    reliability: float
    freshness_seconds: int
    liquidity_score: float


class TradeCreateRequest(BaseModel):
    symbol: str = "BTCUSDT"
    side: Literal["long", "short"] = "long"
    account_equity: float = Field(gt=0)
    risk_amount: float = Field(gt=0)
    entry: float = Field(gt=0)
    stop_loss: float = Field(gt=0)
    take_profit: float = Field(gt=0)
    p_win: float = Field(ge=0.0, le=1.0)
    reliability: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(default=0.55, ge=0.0, le=1.0)
    leverage: float = Field(default=1.0, ge=1.0, le=50.0)
    maker_fee_bps: float | None = Field(default=None, ge=0)
    taker_fee_bps: float | None = Field(default=None, ge=0)
    slippage_bps: float | None = Field(default=None, ge=0)
    liquidity_score: float = Field(default=0.7, ge=0.0, le=1.0)
    freshness_seconds: int = Field(default=15, ge=0)


class TradePatchRequest(BaseModel):
    entry: float | None = Field(default=None, gt=0)
    stop_loss: float | None = Field(default=None, gt=0)
    take_profit: float | None = Field(default=None, gt=0)


class TradeCloseRequest(BaseModel):
    exit_price: float = Field(gt=0)


class PanicCloseRequest(BaseModel):
    trade_ids: list[str] = Field(default_factory=list)


class TradeSnapshot(BaseModel):
    trade_id: str
    symbol: str
    side: str
    state: Literal["idle", "pending", "confirmed", "failed", "closed"]
    entry: float
    stop_loss: float
    take_profit: float
    p_win: float
    reliability: float
    rr: float
    leverage: float
    risk_amount: float
    position_size: float
    created_at: int
    closed_at: int | None = None
    close_price: float | None = None


class PostMortemInsight(BaseModel):
    code: str
    severity: Literal["info", "warning", "critical"]
    message: str
    evidence: dict[str, float | int | str]


class PostMortemResponse(BaseModel):
    trade: TradeSnapshot
    mfe: float
    mae: float
    mfe_r: float
    mae_r: float
    realized_rr: float
    insights: list[PostMortemInsight]
    educational_only: str = "Educational only. Not financial advice. No guaranteed profits."
