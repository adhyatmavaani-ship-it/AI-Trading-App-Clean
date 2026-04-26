from fastapi import APIRouter, Depends, HTTPException

from app.schemas.backtest import (
    BacktestRequest,
    BacktestResponse,
    StrategyOptimizationRequest,
    StrategyOptimizationResponse,
)
from app.services.container import ServiceContainer, get_container

router = APIRouter(prefix="/backtests", tags=["backtests"])


@router.post("/run", response_model=BacktestResponse)
async def run_backtest(
    request: BacktestRequest, container: ServiceContainer = Depends(get_container)
) -> BacktestResponse:
    try:
        return await container.backtesting_engine.run(request)
    except Exception as exc:  # pragma: no cover - integration path
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/optimize", response_model=StrategyOptimizationResponse)
async def optimize_backtest(
    request: StrategyOptimizationRequest,
    container: ServiceContainer = Depends(get_container),
) -> StrategyOptimizationResponse:
    try:
        return await container.backtesting_engine.optimize(request)
    except Exception as exc:  # pragma: no cover - integration path
        raise HTTPException(status_code=500, detail=str(exc)) from exc
