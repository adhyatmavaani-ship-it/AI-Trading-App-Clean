from __future__ import annotations

from fastapi import APIRouter

from db.database import SQLiteTradeDatabase
from engine.meta_engine import MetaEngine


def create_state_router(
    db: SQLiteTradeDatabase,
    meta_engine: MetaEngine,
    strategies: list[str],
) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["state"])

    @router.get("/state")
    def state() -> dict[str, object]:
        normalized_strategies = sorted(set(strategies + db.strategy_names()))
        performance = [
            meta_engine._summarize_strategy(strategy).model_dump()
            for strategy in normalized_strategies
        ]
        return {
            "summary": db.summary(),
            "daily_pnl": db.daily_pnl(),
            "consecutive_losses": db.consecutive_losses(),
            "strategy_performance": performance,
            "recent_trades": [trade.model_dump(mode="json") for trade in db.list_trades(limit=10)],
        }

    return router
