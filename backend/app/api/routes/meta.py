from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.exceptions import AuthenticationError
from app.middleware.auth import get_user_id
from app.schemas.meta import MetaAnalyticsResponse, MetaDecisionResponse
from app.services.container import ServiceContainer, get_container

router = APIRouter(prefix="/meta", tags=["Meta"])


@router.get(
    "/decision/{trade_id}",
    response_model=MetaDecisionResponse,
    summary="Get meta controller decision",
    description="Returns the structured Meta Controller decision log for a trade, including confidence, conflicts, risk adjustments, and health context.",
)
async def get_meta_decision(
    trade_id: str,
    request: Request,
    container: ServiceContainer = Depends(get_container),
) -> MetaDecisionResponse:
    try:
        user_id = get_user_id(request)
        payload = container.meta_controller.get_decision_log(trade_id)
        if payload is None:
            raise HTTPException(status_code=404, detail=f"Meta decision for trade {trade_id} was not found")
        if str(payload.get("user_id", "")) != user_id:
            raise AuthenticationError(
                "Cannot access another user's meta decision",
                error_code="UNAUTHORIZED_RESOURCE_ACCESS",
            )
        return MetaDecisionResponse(**payload)
    except AuthenticationError as exc:
        raise HTTPException(status_code=403, detail=exc.to_dict()) from exc
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/analytics",
    response_model=MetaAnalyticsResponse,
    summary="Get meta controller analytics",
    description="Returns blocked trade stats, strategy performance, and confidence distribution derived from Meta Controller logs.",
)
async def get_meta_analytics(
    request: Request,
    container: ServiceContainer = Depends(get_container),
) -> MetaAnalyticsResponse:
    try:
        get_user_id(request)
        diagnostics = []
        for key in sorted(container.cache.keys("signal:diagnostics:*"))[-container.settings.signal_diagnostics_limit :]:
            payload = container.cache.get_json(key)
            if payload:
                diagnostics.append(payload)
        snapshot = container.meta_controller.analytics_snapshot()
        snapshot["signal_pipeline"] = {
            "count": len(diagnostics),
            "accepted": sum(1 for item in diagnostics if item.get("accepted_trade")),
            "low_confidence": sum(1 for item in diagnostics if item.get("low_confidence")),
            "latest": diagnostics,
        }
        snapshot["learning"] = (
            container.adaptive_learning_service.snapshot()
            if getattr(container, "adaptive_learning_service", None) is not None
            else {}
        )
        return MetaAnalyticsResponse(**snapshot)
    except AuthenticationError as exc:
        raise HTTPException(status_code=403, detail=exc.to_dict()) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc
