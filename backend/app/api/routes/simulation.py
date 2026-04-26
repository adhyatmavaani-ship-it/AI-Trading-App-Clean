from fastapi import APIRouter, Depends, HTTPException

from app.schemas.simulation import PerformanceReport, SimulationRequest, SimulationSummary
from app.services.container import ServiceContainer, get_container

router = APIRouter(prefix="/simulation", tags=["simulation"])


@router.post("/run", response_model=SimulationSummary)
async def run_simulation(
    request: SimulationRequest,
    container: ServiceContainer = Depends(get_container),
) -> SimulationSummary:
    try:
        return await container.simulation_tester.run(request)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/report", response_model=PerformanceReport)
async def simulation_report(
    request: SimulationRequest,
    container: ServiceContainer = Depends(get_container),
) -> PerformanceReport:
    try:
        summary = await container.simulation_tester.run(request)
        return container.simulation_tester.performance_report(summary, request.days)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/generative/{symbol}")
async def generative_simulation(
    symbol: str,
    btc_drop_pct: float = 0.05,
    inflation_surprise: float = 0.02,
    horizon_minutes: int = 15,
    path_count: int = 10000,
    container: ServiceContainer = Depends(get_container),
) -> dict:
    try:
        latest_price = await container.market_data.fetch_latest_price(symbol.upper())
        return container.generative_simulation_engine.dream_market_paths(
            symbol=symbol.upper(),
            base_price=latest_price,
            horizon_minutes=horizon_minutes,
            path_count=path_count,
            shock_scenario={
                "btc_drop_pct": btc_drop_pct,
                "inflation_surprise": inflation_surprise,
            },
        )
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc
