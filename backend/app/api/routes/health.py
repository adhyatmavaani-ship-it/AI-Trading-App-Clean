"""Health check endpoints for system monitoring and Kubernetes integration."""

from datetime import datetime, timezone
import os
from typing import Any

from fastapi import APIRouter, Depends
from starlette.responses import JSONResponse

from app.core.config import get_settings
from app.services.container import ServiceContainer, get_container

router = APIRouter(tags=["health"])


def _render_commit() -> str:
    return os.environ.get("RENDER_GIT_COMMIT", "")


@router.get("/health")
async def healthcheck() -> dict[str, str]:
    """Minimal healthcheck for load balancers."""
    settings = get_settings()
    return {"status": "ok", "version": settings.app_version, "commit": _render_commit()}


@router.get("/health/live")
async def liveness_check() -> dict[str, Any]:
    """Kubernetes liveness probe - is the service running?"""
    settings = get_settings()
    return {
        "status": "alive",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": settings.app_version,
        "commit": _render_commit(),
    }


@router.get("/health/ready")
async def readiness_check(container: ServiceContainer = Depends(get_container)) -> JSONResponse:
    """
    Kubernetes readiness probe - can the service handle traffic?
    Checks all critical dependencies.
    """
    checks: dict[str, str] = {}
    all_ready = True

    try:
        using_fallback = bool(getattr(container.cache, "using_fallback", False))
        if using_fallback:
            checks["redis"] = "degraded_in_memory"
        elif container.cache.client.ping():
            checks["redis"] = "ready"
        else:
            checks["redis"] = "unhealthy"
            all_ready = False
    except Exception as exc:
        checks["redis"] = f"error: {str(exc)[:50]}"
        all_ready = False

    try:
        if container.firestore is None or getattr(container.firestore, "client", None) is None:
            checks["firestore"] = "disabled"
        else:
            collection = container.firestore._collection("health")
            checks["firestore"] = "ready" if collection is not None else "unhealthy"
    except Exception as exc:
        checks["firestore"] = f"error: {str(exc)[:50]}"
        all_ready = False

    try:
        if hasattr(container.market_data, "latest_stream_price") and hasattr(container.market_data, "fetch_latest_price"):
            checks["market_data"] = "ready"
        else:
            checks["market_data"] = "unavailable"
            all_ready = False
    except Exception as exc:
        checks["market_data"] = f"error: {str(exc)[:50]}"
        all_ready = False

    status = "ready" if all_ready else "not_ready"
    status_code = 200 if all_ready else 503
    settings = get_settings()

    return JSONResponse(
        status_code=status_code,
        content={
            "status": status,
            "version": settings.app_version,
            "commit": _render_commit(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": checks,
            "all_ready": all_ready,
        },
    )


@router.get("/health/detailed")
async def detailed_health(container: ServiceContainer = Depends(get_container)) -> dict[str, Any]:
    """Detailed health report with metrics and diagnostics."""
    settings = get_settings()

    details: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": settings.service_name,
        "version": settings.app_version,
        "commit": _render_commit(),
        "environment": settings.environment,
        "trading_mode": settings.trading_mode,
        "dependencies": {},
        "system": {},
        "limits": {},
    }

    try:
        using_fallback = bool(getattr(container.cache, "using_fallback", False))
        details["dependencies"]["redis"] = (
            "in_memory_fallback"
            if using_fallback
            else "connected"
            if container.cache.client.ping()
            else "disconnected"
        )
    except Exception as exc:
        details["dependencies"]["redis"] = f"error: {str(exc)[:50]}"

    try:
        if container.firestore and hasattr(container.firestore, "client") and container.firestore.client is not None:
            details["dependencies"]["firestore"] = "connected"
        else:
            details["dependencies"]["firestore"] = "not_configured"
    except Exception as exc:
        details["dependencies"]["firestore"] = f"error: {str(exc)[:50]}"

    if hasattr(container, "system_monitor"):
        try:
            details["system"]["active_trades"] = getattr(container.system_monitor, "active_trades_count", 0)
            details["system"]["error_count"] = getattr(container.system_monitor, "error_count", 0)
            details["system"]["success_rate"] = getattr(container.system_monitor, "success_rate", 0.0)
        except Exception as exc:
            details["system"]["monitor_error"] = str(exc)[:50]

    details["limits"] = {
        "daily_loss_limit": f"{settings.daily_loss_limit*100:.1f}%",
        "max_coin_exposure": f"{settings.max_coin_exposure_pct*100:.1f}%",
        "max_consecutive_losses": settings.max_consecutive_losses,
        "rate_limit_per_minute": settings.rate_limit_per_minute,
    }

    return details
