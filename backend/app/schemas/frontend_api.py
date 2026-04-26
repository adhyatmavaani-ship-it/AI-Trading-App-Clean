from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class LiveSignalItem(BaseModel):
    signal_id: str = Field(description="Unique signal identifier used for downstream execution and deduplication.", examples=["BTCUSDT:1777155200"])
    symbol: str = Field(description="Market symbol for the live signal.", examples=["BTCUSDT"])
    strategy: str = Field(description="Strategy selected by the strategy engine for this signal.", examples=["TREND_FOLLOW"])
    alpha_score: float = Field(description="Unified alpha score from the alpha decision engine.", examples=[87.4])
    regime: str = Field(description="Detected market regime at signal generation time.", examples=["TRENDING"])
    price: float = Field(description="Reference market price when the signal was generated.", examples=[68250.25])
    signal_version: int = Field(description="Monotonic Redis-backed version for the published signal.", examples=[1452])
    published_at: datetime = Field(description="UTC timestamp when the signal was published to the broadcast layer.")
    decision_reason: str = Field(description="Human-readable reason explaining why the signal was approved or blocked.", examples=["Approved: alpha final score 87.40"])
    degraded_mode: bool = Field(description="Whether the platform was in degraded execution mode when this signal was produced.", examples=[False])
    required_tier: str = Field(description="Minimum user tier required to receive the signal.", examples=["pro"])
    min_balance: float = Field(description="Minimum portfolio balance required to receive the signal.", examples=[25.0])

    model_config = {
        "json_schema_extra": {
            "example": {
                "signal_id": "BTCUSDT:1777155200",
                "symbol": "BTCUSDT",
                "strategy": "TREND_FOLLOW",
                "alpha_score": 87.4,
                "regime": "TRENDING",
                "price": 68250.25,
                "signal_version": 1452,
                "published_at": "2026-04-25T08:15:22Z",
                "decision_reason": "Approved: alpha final score 87.40",
                "degraded_mode": False,
                "required_tier": "pro",
                "min_balance": 25.0,
            }
        }
    }


class LiveSignalsResponse(BaseModel):
    count: int = Field(description="Number of live signals returned.", examples=[3])
    items: list[LiveSignalItem] = Field(description="Most recent cached live signals available for frontend display.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "count": 1,
                "items": [LiveSignalItem.model_config["json_schema_extra"]["example"]],
            }
        }
    }


class VirtualOrderBatchItem(BaseModel):
    aggregate_id: str = Field(description="Internal virtual batch identifier created by the VOM layer.", examples=["d410606d-93f7-4120-b8bb-4dcb9cdb9997"])
    exchange_order_id: str | None = Field(default=None, description="Exchange order identifier for the aggregated parent order.", examples=["884421991"])
    symbol: str = Field(description="Market symbol for the aggregated order batch.", examples=["BTCUSDT"])
    side: str = Field(description="Batch direction applied to all grouped user intents.", examples=["BUY"])
    status: str = Field(description="Current aggregate batch status.", examples=["PARTIALLY_FILLED"])
    requested_quantity: float = Field(description="Total requested quantity across all grouped child intents.", examples=[12.5])
    executed_quantity: float = Field(description="Total quantity executed by the exchange for the aggregate parent order.", examples=[10.0])
    remaining_quantity: float = Field(description="Remaining aggregate quantity awaiting retry or follow-up execution.", examples=[2.5])
    intent_count: int = Field(description="Number of child user intents aggregated into this batch.", examples=[143])
    allocation_count: int = Field(description="Number of child allocations generated from the parent fill.", examples=[143])
    retry_count: int = Field(description="How many retry attempts have been used for this batch.", examples=[1])
    fee_paid: float = Field(description="Total fee paid for the aggregated parent execution.", examples=[4.82])
    executed_price: float = Field(description="Average executed price for the aggregate parent order.", examples=[68192.44])
    updated_at: datetime = Field(description="Most recent UTC timestamp for the aggregate batch state.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "aggregate_id": "d410606d-93f7-4120-b8bb-4dcb9cdb9997",
                "exchange_order_id": "884421991",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "status": "PARTIALLY_FILLED",
                "requested_quantity": 12.5,
                "executed_quantity": 10.0,
                "remaining_quantity": 2.5,
                "intent_count": 143,
                "allocation_count": 143,
                "retry_count": 1,
                "fee_paid": 4.82,
                "executed_price": 68192.44,
                "updated_at": "2026-04-25T08:20:31Z",
            }
        }
    }


class VirtualOrderBatchListResponse(BaseModel):
    count: int = Field(description="Number of virtual order batches returned.", examples=[2])
    items: list[VirtualOrderBatchItem] = Field(description="Current or recently updated virtual order batches.")


class UserPnLResponse(BaseModel):
    user_id: str = Field(description="User identifier for the portfolio snapshot.", examples=["user_123"])
    starting_equity: float = Field(description="Configured baseline equity used to calculate PnL.", examples=[10000.0])
    realized_equity: float = Field(description="Equity after closed-trade realized PnL, before mark-to-market unrealized updates.", examples=[10340.0])
    current_equity: float = Field(description="Latest equity tracked by the drawdown protection engine.", examples=[10425.75])
    absolute_pnl: float = Field(description="Absolute profit or loss relative to starting equity.", examples=[425.75])
    pnl_pct: float = Field(description="Portfolio return percentage relative to starting equity.", examples=[0.042575])
    realized_pnl: float = Field(description="Closed-trade realized PnL booked into the portfolio ledger.", examples=[340.0])
    unrealized_pnl: float = Field(description="Open-position unrealized mark-to-market PnL net of entry fees.", examples=[85.75])
    peak_equity: float = Field(description="Highest observed equity used for drawdown calculations.", examples=[10700.0])
    rolling_drawdown: float = Field(description="Current rolling drawdown percentage.", examples=[0.0256])
    protection_state: str = Field(description="Current drawdown protection state.", examples=["NORMAL"])
    capital_multiplier: float = Field(description="Capital multiplier currently allowed by risk protection.", examples=[1.0])
    active_trades: int = Field(description="Count of currently active trades found for this user in cache state.", examples=[3])
    open_notional: float = Field(description="Entry-notional tied up in open positions.", examples=[1200.0])
    gross_exposure: float = Field(description="Current mark-to-market gross exposure across open positions.", examples=[1285.75])
    winning_trades: int = Field(description="Number of closed winning trades in the cached ledger summary.", examples=[8])
    losing_trades: int = Field(description="Number of closed losing trades in the cached ledger summary.", examples=[3])
    closed_trades: int = Field(description="Number of closed trades recorded in the cached ledger summary.", examples=[11])
    fees_paid: float = Field(description="Cumulative fees recorded by the portfolio ledger.", examples=[22.4])
    positions: list[dict[str, str | float | int]] = Field(default_factory=list, description="Aggregated open positions by symbol and side.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "user_123",
                "starting_equity": 10000.0,
                "realized_equity": 10340.0,
                "current_equity": 10425.75,
                "absolute_pnl": 425.75,
                "pnl_pct": 0.042575,
                "realized_pnl": 340.0,
                "unrealized_pnl": 85.75,
                "peak_equity": 10700.0,
                "rolling_drawdown": 0.0256,
                "protection_state": "NORMAL",
                "capital_multiplier": 1.0,
                "active_trades": 3,
                "open_notional": 1200.0,
                "gross_exposure": 1285.75,
                "winning_trades": 8,
                "losing_trades": 3,
                "closed_trades": 11,
                "fees_paid": 22.4,
                "positions": [
                    {
                        "symbol": "BTCUSDT",
                        "side": "BUY",
                        "quantity": 0.12,
                        "avg_entry_price": 68000.0,
                        "current_price": 68600.0,
                        "market_value": 8232.0,
                        "unrealized_pnl": 72.0,
                        "trade_count": 2,
                    }
                ],
            }
        }
    }


class TradeTimelineEvent(BaseModel):
    timestamp: datetime = Field(description="UTC timestamp associated with the timeline event.")
    stage: str = Field(description="Execution lifecycle stage.", examples=["ORDER_SUBMITTED"])
    status: str = Field(description="State recorded at that lifecycle stage.", examples=["PARTIALLY_FILLED"])
    description: str = Field(description="Human-readable summary of what happened at this stage.", examples=["Exchange order remains partially filled and awaits follow-up reconciliation."])
    metadata: dict[str, str | float | int | bool | None] = Field(default_factory=dict, description="Additional machine-readable details for the timeline event.")


class TradeTimelineResponse(BaseModel):
    trade_id: str = Field(description="Trade identifier requested by the client.", examples=["884421991"])
    current_status: str = Field(description="Current known status for the trade.", examples=["PARTIAL"])
    events: list[TradeTimelineEvent] = Field(description="Chronological trade lifecycle events used by the frontend timeline.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "trade_id": "884421991",
                "current_status": "PARTIAL",
                "events": [
                    {
                        "timestamp": "2026-04-25T08:15:22Z",
                        "stage": "SIGNAL_ACCEPTED",
                        "status": "QUEUED",
                        "description": "Trade signal passed validation and was queued for execution.",
                        "metadata": {"symbol": "BTCUSDT", "side": "BUY"},
                    },
                    {
                        "timestamp": "2026-04-25T08:15:27Z",
                        "stage": "ORDER_SUBMITTED",
                        "status": "PARTIALLY_FILLED",
                        "description": "Exchange order remains partially filled and awaits follow-up reconciliation.",
                        "metadata": {"order_id": "884421991", "remaining_qty": 0.25},
                    },
                ],
            }
        }
    }
