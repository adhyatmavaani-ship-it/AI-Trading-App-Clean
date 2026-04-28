from fastapi import APIRouter, Depends, HTTPException, Request

from app.middleware.auth import can_execute_for_users, get_user_id
from app.services.container import ServiceContainer, get_container

router = APIRouter(prefix="/admin", tags=["Admin"])


def _ensure_admin(request: Request) -> str:
    user_id = get_user_id(request)
    if not can_execute_for_users(request):
        raise HTTPException(
            status_code=403,
            detail={
                "error_code": "ADMIN_PRIVILEGES_REQUIRED",
                "message": "This action requires elevated admin privileges.",
                "details": {},
            },
        )
    return user_id


@router.get("/model/state")
async def get_model_state(
    request: Request,
    container: ServiceContainer = Depends(get_container),
) -> dict:
    actor_user_id = _ensure_admin(request)
    registry = container.trade_probability_engine.registry
    active = registry.load_probability_metadata() or {}
    fallback = registry.load_probability_fallback_metadata() or {}
    latest_event = registry.latest_probability_registry_event() if hasattr(registry, "latest_probability_registry_event") else None
    return {
        "actor_user_id": actor_user_id,
        "active_model": active,
        "fallback_model": fallback,
        "latest_event": latest_event,
        "guard_state": container.retrain_trigger_service.guard_state(),
    }


@router.post("/model/rollback")
async def rollback_model(
    request: Request,
    container: ServiceContainer = Depends(get_container),
) -> dict:
    actor_user_id = _ensure_admin(request)
    registry = container.trade_probability_engine.registry
    restored = registry.activate_probability_fallback() if hasattr(registry, "activate_probability_fallback") else None
    if restored is None:
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "NO_FALLBACK_MODEL",
                "message": "No fallback probability model is available for rollback.",
                "details": {},
            },
        )
    if hasattr(container.trade_probability_engine, "_metadata"):
        container.trade_probability_engine._model = None
        container.trade_probability_engine._scaler = None
        container.trade_probability_engine._metadata = restored
    fallback_metadata = registry.load_probability_fallback_metadata() or {}
    container.model_stability.override_active_model(
        active_model_version=str(restored.get("model_version", "unknown") or "unknown"),
        fallback_model_version=str(fallback_metadata.get("model_version", "") or "") or None,
        degraded=False,
        retraining_triggered=False,
    )
    guard_state = container.retrain_trigger_service.set_manual_rollback_cooldown(actor_user_id=actor_user_id)
    if hasattr(registry, "annotate_latest_probability_event"):
        registry.annotate_latest_probability_event(
            trigger_mode="manual_rollback",
            summary="Manual rollback to stable fallback model by admin override.",
            actor_user_id=actor_user_id,
            cooldown_until=guard_state.get("rollback_cooldown_until"),
        )
    container.cache.set_json(
        "ml:trade_probability:last_update_notice",
        {
            "message": "AI rolled back to the previous stable model by admin safety override.",
            "model_version": str(restored.get("model_version", "unknown") or "unknown"),
            "trigger_mode": "manual_rollback",
            "updated_at": guard_state.get("freeze_updated_at") or registry.latest_probability_registry_event().get("promoted_at"),
        },
        ttl=container.settings.monitor_state_ttl_seconds,
    )
    return {
        "rolled_back": True,
        "active_model_version": restored.get("model_version"),
        "fallback_model_version": fallback_metadata.get("model_version"),
        "guard_state": guard_state,
    }


@router.post("/model/freeze")
async def set_model_freeze(
    enabled: bool,
    request: Request,
    container: ServiceContainer = Depends(get_container),
) -> dict:
    actor_user_id = _ensure_admin(request)
    guard_state = container.retrain_trigger_service.set_freeze(
        enabled=enabled,
        actor_user_id=actor_user_id,
        reason="manual_admin_freeze" if enabled else "manual_admin_unfreeze",
    )
    return {
        "freeze_enabled": guard_state["freeze_enabled"],
        "guard_state": guard_state,
    }
