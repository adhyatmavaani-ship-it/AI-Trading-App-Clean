from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from app.schemas.public_api import (
    PublicDailyItem,
    PublicDailyResponse,
    PublicPerformanceResponse,
    PublicTradeItem,
    PublicTradesResponse,
)
from app.services.container import ServiceContainer, get_container

router = APIRouter(prefix="/public", tags=["Public"])

PUBLIC_CACHE_TTL_SECONDS = 30


@router.get(
    "/performance",
    response_model=PublicPerformanceResponse,
    summary="Get public performance snapshot",
    description="Returns aggregated trading performance for public trust and marketing surfaces. No user-specific data is exposed.",
)
async def get_public_performance(
    container: ServiceContainer = Depends(get_container),
) -> PublicPerformanceResponse:
    cache_key = "public:performance:v1"
    cached = container.cache.get_json(cache_key)
    if cached:
        return PublicPerformanceResponse(**cached)

    summary = container.firestore.load_public_performance_summary()
    response = PublicPerformanceResponse(
        win_rate=float(summary.get("win_rate", 0.0) or 0.0),
        total_pnl_pct=float(summary.get("total_pnl_pct", 0.0) or 0.0),
        total_trades=int(summary.get("total_trades", 0) or 0),
        last_updated=_normalize_datetime(summary.get("last_updated")),
    )
    container.cache.set_json(cache_key, response.model_dump(mode="json"), ttl=PUBLIC_CACHE_TTL_SECONDS)
    return response


@router.get(
    "/trades",
    response_model=PublicTradesResponse,
    summary="Get recent public trade results",
    description="Returns the most recent closed trades with anonymized outcome data only.",
)
async def get_public_trades(
    limit: int = Query(default=20, ge=1, le=100, description="Maximum number of closed trades to return."),
    container: ServiceContainer = Depends(get_container),
) -> PublicTradesResponse:
    cache_key = f"public:trades:v1:{limit}"
    cached = container.cache.get_json(cache_key)
    if cached:
        return PublicTradesResponse(**cached)

    trades = []
    for payload in container.firestore.list_closed_trades(limit=limit):
        pnl_pct = _trade_pnl_pct(payload)
        trades.append(
            PublicTradeItem(
                symbol=str(payload.get("symbol", "")),
                side=str(payload.get("side", "")),
                entry=float(payload.get("entry", 0.0) or 0.0),
                exit=float(payload.get("exit", payload.get("close_price", 0.0)) or 0.0),
                pnl_pct=pnl_pct,
                status="WIN" if pnl_pct >= 0 else "LOSS",
            )
        )
    response = PublicTradesResponse(count=len(trades), items=trades)
    container.cache.set_json(cache_key, response.model_dump(mode="json"), ttl=PUBLIC_CACHE_TTL_SECONDS)
    return response


@router.get(
    "/daily",
    response_model=PublicDailyResponse,
    summary="Get public daily performance",
    description="Returns anonymized daily pnl percentages for marketing and trust dashboards.",
)
async def get_public_daily(
    limit: int = Query(default=90, ge=1, le=365, description="Maximum number of daily points to return."),
    container: ServiceContainer = Depends(get_container),
) -> PublicDailyResponse:
    cache_key = f"public:daily:v1:{limit}"
    cached = container.cache.get_json(cache_key)
    if cached:
        return PublicDailyResponse(**cached)

    rows = [
        PublicDailyItem(
            date=str(item.get("date", "")),
            pnl_pct=float(item.get("pnl_pct", 0.0) or 0.0),
        )
        for item in container.firestore.load_public_daily_results(limit=limit)
    ]
    response = PublicDailyResponse(count=len(rows), items=rows)
    container.cache.set_json(cache_key, response.model_dump(mode="json"), ttl=PUBLIC_CACHE_TTL_SECONDS)
    return response


def _normalize_datetime(value) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def _trade_pnl_pct(payload: dict) -> float:
    entry = float(payload.get("entry", 0.0) or 0.0)
    exit_price = float(payload.get("exit", payload.get("close_price", 0.0)) or 0.0)
    side = str(payload.get("side", "")).upper()
    if entry > 0 and exit_price > 0:
        directional = (exit_price - entry) / entry
        if side == "SELL":
            directional *= -1
        return round(directional * 100, 4)

    realized_pnl = float(payload.get("profit", payload.get("realized_pnl", 0.0)) or 0.0)
    executed_notional = float(
        payload.get(
            "executed_notional",
            (float(payload.get("executed_quantity", 0.0) or 0.0) * entry),
        ) or 0.0
    )
    if executed_notional > 0:
        return round((realized_pnl / executed_notional) * 100, 4)
    return 0.0
