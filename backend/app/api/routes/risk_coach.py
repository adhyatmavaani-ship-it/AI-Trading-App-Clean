from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, HTTPException, Query, WebSocket

from app.core.config import get_settings
from app.schemas.risk_coach import (
    MarketOhlcResponse,
    PanicCloseRequest,
    RiskEvaluationRequest,
    RiskEvaluationResponse,
    TradeCloseRequest,
    TradeCreateRequest,
    TradePatchRequest,
)
from app.services.risk_coach_market import RiskCoachMarketService
from app.services.risk_coach_service import RiskCoachService


router = APIRouter(tags=["Risk Coach"])


@lru_cache
def get_risk_coach_market_service() -> RiskCoachMarketService:
    return RiskCoachMarketService()


@lru_cache
def get_risk_coach_service() -> RiskCoachService:
    return RiskCoachService(get_settings(), get_risk_coach_market_service())


@router.get("/market/ohlc", response_model=MarketOhlcResponse)
async def get_market_ohlc(
    symbol: str = Query(default="BTCUSDT"),
    interval: str = Query(default="1m"),
    limit: int = Query(default=200, ge=1, le=200),
) -> MarketOhlcResponse:
    market = get_risk_coach_market_service()
    return MarketOhlcResponse(
        symbol=symbol.upper(),
        interval=interval,
        stream=f"{symbol.lower()}@kline_{interval}",
        candles=market.latest_candles(limit=limit),
        source=market.source(),
    )


@router.websocket("/ws/market")
async def market_stream(websocket: WebSocket) -> None:
    await get_risk_coach_market_service().connect(websocket)


@router.post("/risk-coach/evaluate", response_model=RiskEvaluationResponse)
async def evaluate_trade(request: RiskEvaluationRequest) -> RiskEvaluationResponse:
    return get_risk_coach_service().evaluate(request)


@router.post("/risk-coach/heatmap")
async def heatmap(request: RiskEvaluationRequest) -> dict[str, object]:
    return {"zone": get_risk_coach_service().build_heatmap(request).model_dump()}


@router.get("/risk-coach/trades")
async def list_trades() -> dict[str, object]:
    return {"items": [trade.model_dump() for trade in get_risk_coach_service().list_trades()]}


@router.post("/risk-coach/trades")
async def create_trade(request: TradeCreateRequest) -> dict[str, object]:
    trade = get_risk_coach_service().create_trade(request)
    return {"trade": trade.model_dump()}


@router.patch("/risk-coach/trades/{trade_id}")
async def patch_trade(trade_id: str, request: TradePatchRequest) -> dict[str, object]:
    service = get_risk_coach_service()
    try:
        trade = service.patch_trade(trade_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Trade not found") from exc
    return {"trade": trade.model_dump()}


@router.post("/risk-coach/trades/{trade_id}/close")
async def close_trade(trade_id: str, request: TradeCloseRequest) -> dict[str, object]:
    service = get_risk_coach_service()
    try:
        report = service.close_trade(trade_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Trade not found") from exc
    return report.model_dump()


@router.post("/risk-coach/panic-close")
async def panic_close(request: PanicCloseRequest) -> dict[str, object]:
    return get_risk_coach_service().panic_close(request)
