from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from engine.monitor_engine import MarketPriceStore, TradeLifecycleLoop
from engine.sync_engine import SyncEngine


class PriceTickPayload(BaseModel):
    symbol: str
    price: float = Field(gt=0)
    run_monitor: bool = True


def create_monitor_router(
    price_store: MarketPriceStore,
    lifecycle_loop: TradeLifecycleLoop,
    sync_engine: SyncEngine | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["monitor"])

    @router.post("/price")
    async def publish_price(payload: PriceTickPayload) -> dict[str, object]:
        normalized_symbol = payload.symbol.strip().upper()
        price_store.set_price(normalized_symbol, payload.price)
        closed = await lifecycle_loop.run_once() if payload.run_monitor else []
        return {
            "symbol": normalized_symbol,
            "price": float(payload.price),
            "closed_trades": [trade.model_dump(mode="json") for trade in closed],
        }

    @router.post("/monitor/run")
    async def run_monitor() -> dict[str, object]:
        closed = await lifecycle_loop.run_once()
        return {
            "closed_trades": [trade.model_dump(mode="json") for trade in closed],
            "closed_count": len(closed),
        }

    @router.post("/sync/run")
    async def run_sync() -> dict[str, object]:
        if sync_engine is None:
            return {
                "closed_trades": [],
                "updated_trades": [],
                "unknown_trades": [],
                "orphan_trades": [],
                "orphan_symbols": [],
                "processed_count": 0,
            }
        result = sync_engine.run_once()
        return {
            "closed_trades": [trade.model_dump(mode="json") for trade in result["closed_trades"]],
            "updated_trades": [trade.model_dump(mode="json") for trade in result["updated_trades"]],
            "unknown_trades": [trade.model_dump(mode="json") for trade in result["unknown_trades"]],
            "orphan_trades": [trade.model_dump(mode="json") for trade in result["orphan_trades"]],
            "orphan_symbols": list(result["orphan_symbols"]),
            "processed_count": int(result["processed_count"]),
        }

    return router
