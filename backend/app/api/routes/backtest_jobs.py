from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import Response

from app.middleware.auth import get_user_id
from app.schemas.backtest_jobs import AsyncBacktestCompareRequest, AsyncBacktestRunRequest, BacktestJobStatusResponse
from app.services.container import ServiceContainer, get_container

router = APIRouter(prefix="/backtest", tags=["backtest"])


@router.post("/run", response_model=BacktestJobStatusResponse)
async def run_backtest_job(
    payload: AsyncBacktestRunRequest,
    request: Request,
    container: ServiceContainer = Depends(get_container),
) -> BacktestJobStatusResponse:
    try:
        user_id = get_user_id(request)
        return container.backtest_job_service.enqueue(request=payload, user_id=user_id)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/compare", response_model=BacktestJobStatusResponse)
async def run_backtest_comparison(
    payload: AsyncBacktestCompareRequest,
    request: Request,
    container: ServiceContainer = Depends(get_container),
) -> BacktestJobStatusResponse:
    try:
        user_id = get_user_id(request)
        return container.backtest_job_service.enqueue_compare(request=payload, user_id=user_id)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/status/{job_id}", response_model=BacktestJobStatusResponse)
async def get_backtest_job_status(
    job_id: str,
    request: Request,
    container: ServiceContainer = Depends(get_container),
) -> BacktestJobStatusResponse:
    try:
        user_id = get_user_id(request)
        status = BacktestJobStatusResponse.model_validate(
            container.backtest_job_service.status(job_id)
        )
        if status.user_id != user_id:
            raise HTTPException(status_code=403, detail="Cannot access another user's backtest job")
        return status
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/export/{job_id}")
async def export_backtest_job(
    job_id: str,
    request: Request,
    container: ServiceContainer = Depends(get_container),
) -> Response:
    try:
        user_id = get_user_id(request)
        status = BacktestJobStatusResponse.model_validate(
            container.backtest_job_service.status(job_id)
        )
        if status.user_id != user_id:
            raise HTTPException(status_code=403, detail="Cannot export another user's backtest job")
        filename, csv_payload = container.backtest_job_service.export_csv(job_id)
        return Response(
            content=csv_payload,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc
