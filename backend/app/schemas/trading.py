from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class FeatureSnapshot(BaseModel):
    symbol: str
    price: float
    timestamp: datetime
    regime: str
    regime_confidence: float = Field(default=0.5, ge=0, le=1)
    volatility: float
    atr: float = 0.0
    order_book_imbalance: float
    features: dict[str, float]


class AIInference(BaseModel):
    price_forecast_return: float
    expected_return: float
    expected_risk: float
    trade_probability: float = Field(ge=0, le=1)
    confidence_score: float = Field(ge=0, le=1)
    decision: Literal["BUY", "SELL", "HOLD"]
    model_version: str
    model_breakdown: dict[str, float] = Field(default_factory=dict)
    reason: str


class WhaleContext(BaseModel):
    score: float = 0.0
    wallet_count: int = 0
    accumulation_score: float = 0.0
    unusual_activity_score: float = 0.0
    new_token_entry: bool = False
    summary: str = ""


class LiquidityContext(BaseModel):
    liquidity_stability: float = 1.0
    ownership_concentration: float = 0.0
    rug_pull_risk: float = 0.0
    lp_burn_detected: bool = False
    liquidity_removed: bool = False


class SentimentContext(BaseModel):
    hype_score: float = 0.0
    narrative: str = "unknown"
    buzz_score: float = 0.0
    volume_alignment: float = 0.0
    topic_clusters: list[str] = Field(default_factory=list)


class SecurityContext(BaseModel):
    honeypot_risk: float = 0.0
    ownership_risk: float = 0.0
    blacklist_risk: float = 0.0
    mint_risk: float = 0.0
    tradable: bool = True
    notes: list[str] = Field(default_factory=list)


class TaxContext(BaseModel):
    estimated_tax: float = 0.0
    lot_method: str = "FIFO"
    tax_loss_harvest_candidate: bool = False


class ExplainabilityContext(BaseModel):
    indicators: dict[str, float] = Field(default_factory=dict)
    whale_summary: str = ""
    sentiment_summary: str = ""
    risk_summary: str = ""
    execution_summary: str = ""
    human_reason: str = ""


class AlphaContext(BaseModel):
    whale: WhaleContext = Field(default_factory=WhaleContext)
    liquidity: LiquidityContext = Field(default_factory=LiquidityContext)
    sentiment: SentimentContext = Field(default_factory=SentimentContext)
    security: SecurityContext = Field(default_factory=SecurityContext)
    tax: TaxContext = Field(default_factory=TaxContext)
    explainability: ExplainabilityContext = Field(default_factory=ExplainabilityContext)


class AlphaDecision(BaseModel):
    final_score: float = 0.0
    expected_return: float = 0.0
    net_expected_return: float = 0.0
    risk_score: float = 0.0
    execution_cost_total: float = 0.0
    allow_trade: bool = False
    weights: dict[str, float] = Field(default_factory=dict)


class SignalResponse(BaseModel):
    symbol: str
    timeframe: str
    snapshot: FeatureSnapshot
    inference: AIInference
    strategy: str
    risk_budget: float
    rollout_capital_fraction: float = 1.0
    alpha: AlphaContext = Field(default_factory=AlphaContext)
    alpha_decision: AlphaDecision = Field(default_factory=AlphaDecision)


class TradeRequest(BaseModel):
    user_id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: float | None = Field(default=None, gt=0)
    order_type: Literal["MARKET", "LIMIT"] = "MARKET"
    limit_price: float | None = None
    confidence: float = Field(ge=0, le=1)
    reason: str
    expected_return: float | None = None
    expected_risk: float | None = None
    feature_snapshot: dict[str, float] = Field(default_factory=dict)
    requested_notional: float | None = None
    signal_id: str | None = None
    alpha_context: AlphaContext = Field(default_factory=AlphaContext)
    alpha_decision: AlphaDecision = Field(default_factory=AlphaDecision)
    strategy: str = ""
    macro_bias_multiplier: float | None = Field(default=None, gt=0)
    macro_bias_regime: str | None = None


class TradeResponse(BaseModel):
    trade_id: str
    status: str
    trading_mode: Literal["paper", "live"]
    symbol: str
    side: str
    executed_price: float
    executed_quantity: float
    stop_loss: float
    trailing_stop_pct: float
    take_profit: float = 0.0
    fee_paid: float
    slippage_bps: float
    filled_ratio: float
    duplicate_signal: bool = False
    rollout_capital_fraction: float = 1.0
    explanation: str = ""
    alpha_score: float = 0.0
    macro_bias_multiplier: float = 1.0
    macro_bias_regime: str = "NEUTRAL"


class TradeCloseRequest(BaseModel):
    user_id: str
    trade_id: str
    exit_price: float = Field(gt=0)
    closed_quantity: float | None = Field(default=None, gt=0)
    exit_fee: float = Field(default=0.0, ge=0.0)
    reason: str = "manual_close"


class TradeCloseResponse(BaseModel):
    trade_id: str
    user_id: str
    symbol: str
    side: str
    status: str
    closed_quantity: float
    remaining_quantity: float
    exit_price: float
    exit_fee: float
    realized_pnl: float
    current_equity: float
    protection_state: str
