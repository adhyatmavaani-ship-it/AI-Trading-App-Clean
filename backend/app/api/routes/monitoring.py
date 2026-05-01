from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from starlette.responses import Response

from app.core.config import get_settings
from app.core.metrics import get_metrics
from app.middleware.auth import get_user_id
from app.schemas.monitoring import (
    ModelPromotionEvent,
    ModelStabilityStatus,
    ModelStabilityConcentrationHistoryEntry,
    ModelStabilityConcentrationHistoryResponse,
    ModelUpdateNotice,
    PortfolioConcentrationHistoryResponse,
    PortfolioConcentrationSnapshot,
    PortfolioConcentrationStatus,
    SystemHealthResponse,
)
from app.services.container import ServiceContainer, get_container

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])


@router.get(
    "/system",
    response_model=SystemHealthResponse,
    summary="Get system health",
    description="Returns platform-wide health, latency, execution, drawdown, rollout, and model stability metrics used by operational dashboards.",
)
async def system_health(
    request: Request,
    container: ServiceContainer = Depends(get_container),
) -> SystemHealthResponse:
    try:
        user_id = get_user_id(request)
        portfolio_summary = (
            await container.portfolio_ledger.portfolio_concentration_profile(user_id)
            if getattr(container, "portfolio_ledger", None) is not None
            else {}
        )
        container.system_monitor.update_portfolio_concentration(portfolio_summary)
        if hasattr(container.model_stability, "update_concentration_state"):
            container.model_stability.update_concentration_state(portfolio_summary)
        return container.system_monitor.snapshot(
            drawdown=container.drawdown_protection.load(user_id),
            rollout=container.rollout_manager.status(),
            model_stability=container.model_stability.load_status(),
            portfolio_concentration=_portfolio_concentration_status(portfolio_summary),
        )
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/concentration",
    response_model=PortfolioConcentrationHistoryResponse,
    summary="Get portfolio concentration drift history",
    description="Returns the latest portfolio concentration profile plus recent drift history for the authenticated user.",
)
async def concentration_history(
    request: Request,
    window: str = Query(default="24h", pattern=r"^(1h|24h|7d)$"),
    limit: int = Query(default=50, ge=1, le=500),
    container: ServiceContainer = Depends(get_container),
) -> PortfolioConcentrationHistoryResponse:
    try:
        user_id = get_user_id(request)
        if getattr(container, "portfolio_ledger", None) is None:
            empty = PortfolioConcentrationSnapshot()
            return PortfolioConcentrationHistoryResponse(latest=empty, history=[])
        latest_summary = await container.portfolio_ledger.portfolio_concentration_profile(user_id)
        container.system_monitor.update_portfolio_concentration(latest_summary)
        if hasattr(container.model_stability, "update_concentration_state"):
            container.model_stability.update_concentration_state(latest_summary)
        cutoff = _history_cutoff(window, reference_at=latest_summary.get("updated_at"))
        history = [
            _portfolio_concentration_snapshot(snapshot)
            for snapshot in container.portfolio_ledger.concentration_history(user_id)
            if _snapshot_in_window(snapshot, cutoff)
        ]
        history = history[-limit:]
        return PortfolioConcentrationHistoryResponse(
            latest=_portfolio_concentration_snapshot(latest_summary),
            history=history,
        )
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/model-stability/concentration",
    response_model=ModelStabilityConcentrationHistoryResponse,
    summary="Get model-stability concentration drift history",
    description="Returns the latest model stability state plus recent concentration drift history used to throttle trading frequency.",
)
async def model_stability_concentration_history(
    request: Request,
    window: str = Query(default="24h", pattern=r"^(1h|24h|7d)$"),
    limit: int = Query(default=50, ge=1, le=500),
    container: ServiceContainer = Depends(get_container),
) -> ModelStabilityConcentrationHistoryResponse:
    try:
        user_id = get_user_id(request)
        if getattr(container, "portfolio_ledger", None) is not None:
            latest_summary = await container.portfolio_ledger.portfolio_concentration_profile(user_id)
            container.system_monitor.update_portfolio_concentration(latest_summary)
            if hasattr(container.model_stability, "update_concentration_state"):
                container.model_stability.update_concentration_state(latest_summary)
        latest_status = _model_stability_status(container.model_stability.load_status())
        reference_at = None
        history_source = getattr(container.model_stability, "concentration_history", lambda: [])()
        if history_source:
            reference_at = history_source[-1].get("updated_at")
        cutoff = _history_cutoff(window, reference_at=reference_at)
        history = [
            _model_stability_concentration_entry(entry)
            for entry in history_source
            if _snapshot_in_window(entry, cutoff)
        ]
        history = history[-limit:]
        latest_state = history[-1] if history else _model_stability_concentration_entry({})
        latest_notice = None
        latest_notice_payload = container.cache.get_json("ml:trade_probability:last_update_notice")
        if latest_notice_payload:
            latest_notice = ModelUpdateNotice(**latest_notice_payload)
        latest_promotion = None
        trade_probability_engine = getattr(container, "trade_probability_engine", None)
        registry = getattr(trade_probability_engine, "registry", None)
        if hasattr(registry, "latest_probability_registry_event"):
            latest_event = registry.latest_probability_registry_event()
            if latest_event:
                latest_promotion = ModelPromotionEvent(**latest_event)
        return ModelStabilityConcentrationHistoryResponse(
            latest_status=latest_status,
            latest_state=latest_state,
            history=history,
            latest_notice=latest_notice,
            latest_promotion=latest_promotion,
        )
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/metrics",
    summary="Signal pipeline metrics",
    description="Returns live signal pipeline diagnostics, recent decisions, and rejection reasons for debugging signal generation.",
)
async def signal_pipeline_metrics(
    container: ServiceContainer = Depends(get_container),
) -> dict:
    diagnostics = []
    for key in sorted(container.cache.keys("signal:diagnostics:*"))[-container.settings.signal_diagnostics_limit :]:
        payload = container.cache.get_json(key)
        if payload:
            diagnostics.append(payload)
    accepted = sum(1 for item in diagnostics if item.get("accepted_trade"))
    low_confidence = sum(1 for item in diagnostics if item.get("low_confidence"))
    rejection_reasons: dict[str, int] = {}
    for item in diagnostics:
        reason = str(item.get("rejection_reason", "") or "").strip()
        if reason:
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
    return {
        "count": len(diagnostics),
        "accepted": accepted,
        "low_confidence": low_confidence,
        "rejection_reasons": rejection_reasons,
        "latest": diagnostics[-container.settings.signal_diagnostics_limit :],
    }


@router.get(
    "/metrics/prometheus",
    summary="Prometheus metrics",
    description="Returns metrics in Prometheus text format for scraping.",
    include_in_schema=False,
)
async def prometheus_metrics() -> Response:
    """Prometheus-compatible metrics endpoint for monitoring systems."""
    return Response(content=get_metrics(), media_type="text/plain; charset=utf-8")


def _portfolio_concentration_status(summary: dict) -> PortfolioConcentrationStatus:
    snapshot = _portfolio_concentration_snapshot(summary)
    payload = snapshot.model_dump()
    payload.pop("updated_at", None)
    return PortfolioConcentrationStatus(**payload)


def _portfolio_concentration_snapshot(summary: dict) -> PortfolioConcentrationSnapshot:
    severity, severity_reason = _concentration_severity(summary)
    symbol_pct = summary.get("symbol_exposure_pct") or {}
    gross_exposure_pct = float(summary.get("gross_exposure_pct", 0.0) or 0.0)
    side_pct = summary.get("side_exposure_pct") or {}
    theme_pct = summary.get("theme_exposure_pct") or {}
    cluster_pct = summary.get("cluster_exposure_pct") or {}
    beta_pct = summary.get("beta_bucket_exposure_pct") or {}
    dominant_symbol = max(symbol_pct, key=symbol_pct.get) if symbol_pct else None
    dominant_side = max(side_pct, key=side_pct.get) if side_pct else None
    dominant_theme = max(theme_pct, key=theme_pct.get) if theme_pct else None
    dominant_cluster = max(cluster_pct, key=cluster_pct.get) if cluster_pct else None
    dominant_beta_bucket = max(beta_pct, key=beta_pct.get) if beta_pct else None
    sleeve_budget_deltas = {
        str(sleeve): float(value)
        for sleeve, value in (summary.get("factor_sleeve_budget_deltas") or {}).items()
    }
    top_budget_gaining_sleeves = [
        sleeve
        for sleeve, delta in sorted(sleeve_budget_deltas.items(), key=lambda item: item[1], reverse=True)
        if delta > 0
    ][:3]
    top_budget_losing_sleeves = [
        sleeve
        for sleeve, delta in sorted(sleeve_budget_deltas.items(), key=lambda item: item[1])
        if delta < 0
    ][:3]
    return PortfolioConcentrationSnapshot(
        updated_at=summary.get("updated_at"),
        gross_exposure_pct=gross_exposure_pct,
        max_symbol_exposure_pct=max((float(value) for value in symbol_pct.values()), default=0.0),
        max_side_exposure_pct=max((float(value) for value in side_pct.values()), default=0.0),
        max_theme_exposure_pct=max((float(value) for value in theme_pct.values()), default=0.0),
        max_cluster_exposure_pct=max((float(value) for value in cluster_pct.values()), default=0.0),
        max_beta_bucket_exposure_pct=max((float(value) for value in beta_pct.values()), default=0.0),
        gross_exposure_drift=float(summary.get("gross_exposure_drift", 0.0) or 0.0),
        cluster_concentration_drift=float(summary.get("cluster_concentration_drift", 0.0) or 0.0),
        beta_bucket_concentration_drift=float(summary.get("beta_bucket_concentration_drift", 0.0) or 0.0),
        cluster_turnover=float(summary.get("cluster_turnover", 0.0) or 0.0),
        factor_sleeve_budget_turnover=float(summary.get("factor_sleeve_budget_turnover", 0.0) or 0.0),
        max_factor_sleeve_budget_gap_pct=float(summary.get("max_factor_sleeve_budget_gap_pct", 0.0) or 0.0),
        severity=severity,
        severity_reason=severity_reason,
        factor_regime=str(summary.get("factor_regime", "RANGING") or "RANGING"),
        factor_model=str(summary.get("factor_model", "pca_covariance_regime_universe_v1") or "pca_covariance_regime_universe_v1"),
        factor_universe_symbols=[
            str(symbol)
            for symbol in (summary.get("factor_universe_symbols") or [])
            if str(symbol).strip()
        ],
        factor_weights={
            str(symbol): float(weight)
            for symbol, weight in (summary.get("factor_weights") or {}).items()
        },
        factor_attribution={
            str(symbol): float(weight)
            for symbol, weight in (summary.get("factor_attribution") or {}).items()
        },
        factor_sleeve_performance={
            str(sleeve): {
                str(key): value
                for key, value in dict(metrics or {}).items()
            }
            for sleeve, metrics in (summary.get("factor_sleeve_performance") or {}).items()
        },
        factor_sleeve_budget_targets={
            str(sleeve): float(value)
            for sleeve, value in (summary.get("factor_sleeve_budget_targets") or {}).items()
        },
        factor_sleeve_budget_deltas=sleeve_budget_deltas,
        dominant_factor_sleeve=str(summary.get("dominant_factor_sleeve")) if summary.get("dominant_factor_sleeve") else None,
        dominant_symbol=dominant_symbol,
        dominant_side=dominant_side,
        dominant_theme=dominant_theme,
        dominant_cluster=dominant_cluster,
        dominant_beta_bucket=dominant_beta_bucket,
        dominant_over_budget_sleeve=str(summary.get("dominant_over_budget_sleeve")) if summary.get("dominant_over_budget_sleeve") else None,
        dominant_under_budget_sleeve=str(summary.get("dominant_under_budget_sleeve")) if summary.get("dominant_under_budget_sleeve") else None,
        top_budget_gaining_sleeves=top_budget_gaining_sleeves,
        top_budget_losing_sleeves=top_budget_losing_sleeves,
        symbol_count=len(symbol_pct),
        theme_count=len(theme_pct),
        cluster_count=len(cluster_pct),
        beta_bucket_count=len(beta_pct),
    )


def _model_stability_concentration_entry(entry: dict) -> ModelStabilityConcentrationHistoryEntry:
    severity, severity_reason = _model_concentration_severity(entry)
    return ModelStabilityConcentrationHistoryEntry(
        updated_at=entry.get("updated_at"),
        score=float(entry.get("score", 0.0) or 0.0),
        gross_exposure_drift=float(entry.get("gross_exposure_drift", 0.0) or 0.0),
        cluster_concentration_drift=float(entry.get("cluster_concentration_drift", 0.0) or 0.0),
        beta_bucket_concentration_drift=float(entry.get("beta_bucket_concentration_drift", 0.0) or 0.0),
        cluster_turnover=float(entry.get("cluster_turnover", 0.0) or 0.0),
        factor_sleeve_budget_turnover=float(entry.get("factor_sleeve_budget_turnover", 0.0) or 0.0),
        max_factor_sleeve_budget_gap_pct=float(entry.get("max_factor_sleeve_budget_gap_pct", 0.0) or 0.0),
        severity=severity,
        severity_reason=severity_reason,
    )


def _model_stability_status(status: object) -> ModelStabilityStatus:
    if isinstance(status, ModelStabilityStatus):
        return status
    if isinstance(status, dict):
        return ModelStabilityStatus(**status)
    if hasattr(status, "model_dump"):
        return ModelStabilityStatus(**status.model_dump())
    payload = {
        "active_model_version": getattr(status, "active_model_version", "unknown"),
        "fallback_model_version": getattr(status, "fallback_model_version", None),
        "live_win_rate": float(getattr(status, "live_win_rate", 0.0) or 0.0),
        "training_win_rate": float(getattr(status, "training_win_rate", 0.0) or 0.0),
        "drift_score": float(getattr(status, "drift_score", 0.0) or 0.0),
        "calibration_error": float(getattr(status, "calibration_error", 0.0) or 0.0),
        "feature_drift_score": float(getattr(status, "feature_drift_score", 0.0) or 0.0),
        "concept_drift_score": float(getattr(status, "concept_drift_score", 0.0) or 0.0),
        "concentration_drift_score": float(getattr(status, "concentration_drift_score", 0.0) or 0.0),
        "retraining_triggered": bool(getattr(status, "retraining_triggered", False)),
        "trading_frequency_multiplier": float(getattr(status, "trading_frequency_multiplier", 1.0) or 1.0),
        "degraded": bool(getattr(status, "degraded", False)),
    }
    return ModelStabilityStatus(**payload)


def _concentration_severity(summary: dict) -> tuple[str, str | None]:
    settings = get_settings()
    gross_drift = abs(float(summary.get("gross_exposure_drift", 0.0) or 0.0))
    cluster_drift = abs(float(summary.get("cluster_concentration_drift", 0.0) or 0.0))
    beta_drift = abs(float(summary.get("beta_bucket_concentration_drift", 0.0) or 0.0))
    turnover = abs(float(summary.get("cluster_turnover", 0.0) or 0.0))
    budget_gap = abs(float(summary.get("max_factor_sleeve_budget_gap_pct", 0.0) or 0.0))
    budget_turnover = abs(float(summary.get("factor_sleeve_budget_turnover", 0.0) or 0.0))
    peak_drift = max(gross_drift, cluster_drift, beta_drift, budget_gap)

    if peak_drift >= settings.portfolio_concentration_hard_alert_drift:
        return "alert", _concentration_reason(gross_drift, cluster_drift, beta_drift, turnover, budget_gap, budget_turnover)
    if turnover >= settings.portfolio_concentration_hard_turnover:
        return "alert", "Cluster turnover spiking"
    if budget_turnover >= settings.portfolio_concentration_hard_turnover:
        return "alert", "Sleeve budget turnover spiking"
    if peak_drift >= settings.portfolio_concentration_soft_alert_drift:
        return "softening", _concentration_reason(gross_drift, cluster_drift, beta_drift, turnover, budget_gap, budget_turnover)
    if turnover >= settings.portfolio_concentration_soft_turnover:
        return "softening", "Cluster turnover rising"
    if budget_turnover >= settings.portfolio_concentration_soft_turnover:
        return "softening", "Sleeve budget turnover rising"
    return "normal", None


def _concentration_reason(
    gross_drift: float,
    cluster_drift: float,
    beta_drift: float,
    turnover: float,
    budget_gap: float,
    budget_turnover: float,
) -> str:
    signals = {
        "Gross exposure drift rising": gross_drift,
        "Cluster concentration drifting": cluster_drift,
        "Beta bucket concentration drifting": beta_drift,
        "Cluster turnover rising": turnover,
        "Sleeve budget gap widening": budget_gap,
        "Sleeve budget turnover rising": budget_turnover,
    }
    return max(signals, key=signals.get)


def _model_concentration_severity(entry: dict) -> tuple[str, str | None]:
    settings = get_settings()
    score = abs(float(entry.get("score", 0.0) or 0.0))
    turnover = abs(float(entry.get("cluster_turnover", 0.0) or 0.0))
    budget_turnover = abs(float(entry.get("factor_sleeve_budget_turnover", 0.0) or 0.0))
    budget_gap = abs(float(entry.get("max_factor_sleeve_budget_gap_pct", 0.0) or 0.0))
    if score >= settings.probability_concentration_drift_threshold:
        return "alert", "Model throttling drift breached retraining threshold"
    if turnover >= settings.probability_concentration_turnover_threshold:
        return "alert", "Model throttling turnover is unstable"
    if budget_turnover >= settings.portfolio_concentration_hard_turnover:
        return "alert", "Model throttling sleeve budget turnover is unstable"
    if budget_gap >= settings.portfolio_concentration_hard_alert_drift:
        return "alert", "Model throttling sleeve budget gap is unstable"
    if score >= settings.probability_concentration_reduction_threshold:
        return "softening", "Trading frequency softened due to concentration drift"
    if budget_turnover >= settings.portfolio_concentration_soft_turnover:
        return "softening", "Trading frequency softened due to sleeve budget turnover"
    if budget_gap >= settings.portfolio_concentration_soft_alert_drift:
        return "softening", "Trading frequency softened due to sleeve budget gap"
    return "normal", None


def _history_cutoff(window: str, reference_at: str | datetime | None = None) -> datetime:
    mapping = {
        "1h": timedelta(hours=1),
        "24h": timedelta(hours=24),
        "7d": timedelta(days=7),
    }
    reference = _coerce_history_datetime(reference_at) or datetime.now(timezone.utc)
    return reference - mapping.get(window, timedelta(hours=24))


def _coerce_history_datetime(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _snapshot_in_window(snapshot: dict, cutoff: datetime) -> bool:
    updated_at = snapshot.get("updated_at")
    parsed = _coerce_history_datetime(updated_at)
    if parsed is None:
        return False
    return parsed >= cutoff
