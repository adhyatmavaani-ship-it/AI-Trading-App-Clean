from __future__ import annotations

from datetime import datetime, timezone
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.exceptions import AuthenticationError
from app.middleware.auth import get_user_id
from app.schemas.frontend_api import (
    LiveSignalItem,
    LiveSignalsResponse,
    TradeTimelineEvent,
    TradeTimelineResponse,
    UserPnLResponse,
    VirtualOrderBatchItem,
    VirtualOrderBatchListResponse,
)
from app.schemas.trading import SignalResponse
from app.services.container import ServiceContainer, get_container

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/signals/live",
    response_model=LiveSignalsResponse,
    tags=["Signals"],
    summary="List live signals",
    description="Returns the latest cached live signals that were published by the central signal engine and are available for frontend dashboards.",
)
async def get_live_signals(
    limit: int = Query(default=25, ge=1, le=200, description="Maximum number of live signals to return."),
    request: Request = ...,
    container: ServiceContainer = Depends(get_container),
) -> LiveSignalsResponse:
    try:
        try:
            authenticated_user_id = get_user_id(request)
        except AuthenticationError:
            authenticated_user_id = "anonymous"
        viewer_subscription = _load_viewer_signal_subscription(container, authenticated_user_id)
        logger.info("Live signal generation triggered")
        signals = await _generate_live_signals(container, limit=min(limit, 3))
        if len(signals) < min(limit, 3):
            cached_signals = await _collect_live_signals(container, viewer_subscription)
            seen_ids = {item.signal_id for item in signals}
            signals.extend(item for item in cached_signals if item.signal_id not in seen_ids)
        if not signals:
            signals = _fallback_live_signals(container, limit=min(limit, 3))
        ordered = sorted(signals, key=lambda item: item.published_at, reverse=True)[:limit]
        return LiveSignalsResponse(count=len(ordered), items=ordered)
    except AuthenticationError as exc:
        raise HTTPException(status_code=403, detail=exc.to_dict()) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/activity/live",
    tags=["Signals"],
    summary="Get latest bot activity",
    description="Returns the latest scanning or execution activity emitted by the user experience engine.",
)
async def get_live_activity(
    container: ServiceContainer = Depends(get_container),
) -> dict:
    activity_engine = getattr(container, "user_experience_engine", None)
    return activity_engine.latest() if activity_engine is not None else {}


@router.get(
    "/activity/history",
    tags=["Signals"],
    summary="Get recent bot activity feed",
    description="Returns recent scanning, rejection, almost-trade, and execution activity messages.",
)
async def get_activity_history(
    limit: int = Query(default=25, ge=1, le=200, description="Maximum number of activity items to return."),
    container: ServiceContainer = Depends(get_container),
) -> dict:
    activity_engine = getattr(container, "user_experience_engine", None)
    items = activity_engine.history(limit=limit) if activity_engine is not None else []
    return {"count": len(items), "items": items}


@router.get(
    "/activity/readiness",
    tags=["Signals"],
    summary="Get symbol readiness board",
    description="Returns the latest readiness and intent state for the most recently scanned symbols.",
)
async def get_activity_readiness(
    limit: int = Query(default=8, ge=1, le=50, description="Maximum number of readiness cards to return."),
    container: ServiceContainer = Depends(get_container),
) -> dict:
    activity_engine = getattr(container, "user_experience_engine", None)
    items = activity_engine.readiness(limit=limit) if activity_engine is not None else []
    return {"count": len(items), "items": items}


async def _collect_live_signals(container: ServiceContainer, viewer_subscription: dict) -> list[LiveSignalItem]:
    signals: list[LiveSignalItem] = []
    for key in container.cache.keys("signal:latest:*"):
        payload = container.cache.get_json(key)
        if not payload:
            continue
        if not _signal_visible_to_viewer(container, payload, viewer_subscription):
            continue
        alpha_decision = payload.get("alpha_decision", {})
        signals.append(
            LiveSignalItem(
                signal_id=str(payload.get("signal_id", "")),
                symbol=str(payload.get("symbol", "")),
                action=str(payload.get("action", payload.get("strategy_signal", payload.get("strategy", "HOLD")))),
                strategy=str(payload.get("strategy", "NO_TRADE")),
                confidence=float(payload.get("confidence", payload.get("trade_success_probability", payload.get("strategy_confidence", 0.0)))),
                alpha_score=float(alpha_decision.get("final_score", payload.get("alpha_score", 0.0))),
                regime=str(payload.get("regime", "UNKNOWN")),
                price=float(payload.get("price", 0.0)),
                signal_version=int(payload.get("signal_version", 0)),
                published_at=payload.get("published_at", datetime.now(timezone.utc).isoformat()),
                decision_reason=str(payload.get("decision_reason", "")),
                degraded_mode=bool(payload.get("degraded_mode", False)),
                required_tier=str(payload.get("required_tier", "free")),
                min_balance=float(payload.get("min_balance", 0.0)),
                rejection_reason=str(payload.get("rejection_reason")) if payload.get("rejection_reason") else None,
                low_confidence=bool(payload.get("low_confidence", False)),
            )
        )
    return signals


async def _generate_live_signals(container: ServiceContainer, limit: int = 3) -> list[LiveSignalItem]:
    generated: list[LiveSignalItem] = []
    target = max(1, min(limit, 3))
    trading_orchestrator = getattr(container, "trading_orchestrator", None)
    if trading_orchestrator is None:
        return []
    for signal in await trading_orchestrator.generate_live_signals(limit=target):
        generated.append(_live_signal_from_response(container, signal))
    if len(generated) < target:
        generated.extend(_fallback_live_signals(container, limit=target - len(generated), existing_symbols={item.symbol for item in generated}))
    return generated[:target]


def _live_signal_from_response(container: ServiceContainer, signal: SignalResponse) -> LiveSignalItem:
    confidence = float(signal.inference.confidence_score)
    low_confidence = bool(
        signal.strategy == "LOW_CONFIDENCE_WATCHLIST"
        or confidence < max(container.settings.signal_min_publish_confidence, 0.4)
        or not signal.alpha_decision.allow_trade
    )
    action = signal.inference.decision
    if action == "HOLD":
        action = "BUY" if float(signal.snapshot.features.get("15m_ema_spread", 0.0)) >= 0 else "SELL"
    rejection_reason = None
    if signal.inference.model_version == "best_effort_watchlist":
        rejection_reason = "best_effort_generation"
    elif not signal.alpha_decision.allow_trade:
        rejection_reason = "alpha_engine_rejected"
    elif low_confidence:
        rejection_reason = "low_confidence_watchlist"
    alpha_score = float(signal.alpha_decision.final_score)
    required_tier = "free" if low_confidence else "vip" if alpha_score >= 90 else "pro" if alpha_score >= 80 else "free"
    min_balance = 0.0 if low_confidence else max(container.settings.exchange_min_notional, 25.0 if alpha_score >= 80 else container.settings.exchange_min_notional)
    published_at = signal.snapshot.timestamp
    return LiveSignalItem(
        signal_id=f"{signal.symbol}:generated:{int(published_at.timestamp())}",
        symbol=signal.symbol,
        action=action,
        strategy=signal.strategy,
        confidence=confidence,
        alpha_score=alpha_score,
        regime=str(signal.snapshot.regime),
        price=float(signal.snapshot.price),
        signal_version=0,
        published_at=published_at,
        decision_reason=signal.inference.reason,
        degraded_mode=signal.strategy == "NO_TRADE",
        required_tier=required_tier,
        min_balance=min_balance,
        rejection_reason=rejection_reason,
        low_confidence=low_confidence,
    )


def _fallback_live_signals(
    container: ServiceContainer,
    limit: int = 3,
    existing_symbols: set[str] | None = None,
) -> list[LiveSignalItem]:
    existing_symbols = existing_symbols or set()
    settings = getattr(container, "settings", None)
    websocket_symbols = getattr(settings, "websocket_symbols", None)
    signal_min_publish_confidence = float(getattr(settings, "signal_min_publish_confidence", 0.2))
    alpha_trade_threshold = float(getattr(settings, "alpha_trade_threshold", 5.0))
    candidates = list(websocket_symbols or ["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    now = datetime.now(timezone.utc)
    items: list[LiveSignalItem] = []
    for index, symbol in enumerate(candidates):
        normalized = str(symbol).upper()
        if normalized in existing_symbols:
            continue
        action = "BUY" if index % 2 == 0 else "SELL"
        items.append(
            LiveSignalItem(
                signal_id=f"{normalized}:fallback:{int(now.timestamp())}:{index}",
                symbol=normalized,
                action=action,
                strategy="LOW_CONFIDENCE_WATCHLIST",
                confidence=max(0.2, signal_min_publish_confidence),
                alpha_score=max(0.0, alpha_trade_threshold - 5.0),
                regime="RANGING",
                price=0.0,
                signal_version=0,
                published_at=now,
                decision_reason="Fallback watchlist signal generated to preserve visibility while live evaluation is unavailable.",
                degraded_mode=True,
                required_tier="free",
                min_balance=0.0,
                rejection_reason="live_generation_unavailable",
                low_confidence=True,
            )
        )
        if len(items) >= max(1, limit):
            break
    return items


@router.get(
    "/vom/batches",
    response_model=VirtualOrderBatchListResponse,
    tags=["Virtual Order Batches"],
    summary="List VOM batches",
    description="Returns active or recently updated virtual order management batches used to aggregate child user orders into fewer exchange executions.",
)
async def get_vom_batches(
    limit: int = Query(default=50, ge=1, le=500, description="Maximum number of virtual order batches to return."),
    request: Request = ...,
    container: ServiceContainer = Depends(get_container),
) -> VirtualOrderBatchListResponse:
    try:
        authenticated_user_id = get_user_id(request)
        batches: list[VirtualOrderBatchItem] = []
        for key in container.cache.keys("vom:aggregate:*"):
            payload = container.cache.get_json(key)
            if not payload:
                continue
            if not _batch_visible_to_user(payload, authenticated_user_id):
                continue
            batches.append(VirtualOrderBatchItem(**payload))
        ordered = sorted(batches, key=lambda item: item.updated_at, reverse=True)[:limit]
        return VirtualOrderBatchListResponse(count=len(ordered), items=ordered)
    except AuthenticationError as exc:
        raise HTTPException(status_code=403, detail=exc.to_dict()) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/user/pnl",
    response_model=UserPnLResponse,
    tags=["User Portfolio"],
    summary="Get user PnL",
    description="Returns the current portfolio equity, PnL, and drawdown protection state for a user.",
)
async def get_user_pnl(
    user_id: str = Query(..., description="User identifier whose portfolio snapshot should be returned."),
    request: Request = ...,
    container: ServiceContainer = Depends(get_container),
) -> UserPnLResponse:
    try:
        authenticated_user_id = get_user_id(request)
        _ensure_user_access(authenticated_user_id, user_id)
        ledger_snapshot = await container.portfolio_ledger.portfolio_snapshot(user_id)
        drawdown = container.drawdown_protection.load(user_id)
        return UserPnLResponse(
            user_id=user_id,
            starting_equity=ledger_snapshot["starting_equity"],
            realized_equity=ledger_snapshot["realized_equity"],
            current_equity=ledger_snapshot["current_equity"],
            absolute_pnl=ledger_snapshot["absolute_pnl"],
            pnl_pct=ledger_snapshot["pnl_pct"],
            realized_pnl=ledger_snapshot["realized_pnl"],
            unrealized_pnl=ledger_snapshot["unrealized_pnl"],
            peak_equity=ledger_snapshot["peak_equity"],
            rolling_drawdown=ledger_snapshot["rolling_drawdown"],
            protection_state=drawdown.state,
            capital_multiplier=container.drawdown_protection.capital_multiplier(user_id),
            active_trades=ledger_snapshot["active_trades"],
            open_notional=ledger_snapshot["open_notional"],
            gross_exposure=ledger_snapshot["gross_exposure"],
            winning_trades=ledger_snapshot["winning_trades"],
            losing_trades=ledger_snapshot["losing_trades"],
            closed_trades=ledger_snapshot["closed_trades"],
            fees_paid=ledger_snapshot["fees_paid"],
            positions=ledger_snapshot["positions"],
        )
    except AuthenticationError as exc:
        raise HTTPException(status_code=403, detail=exc.to_dict()) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/trades/active",
    tags=["User Portfolio"],
    summary="List active trades",
    description="Returns currently active trades for the authenticated user.",
)
async def get_active_trades(
    user_id: str = Query(..., description="User identifier whose active trades should be returned."),
    request: Request = ...,
    container: ServiceContainer = Depends(get_container),
) -> dict:
    try:
        authenticated_user_id = get_user_id(request)
        _ensure_user_access(authenticated_user_id, user_id)
        analytics = getattr(container, "analytics_service", None)
        items = analytics.active_trades(user_id) if analytics is not None else []
        return {"count": len(items), "items": items}
    except AuthenticationError as exc:
        raise HTTPException(status_code=403, detail=exc.to_dict()) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/trades/history",
    tags=["User Portfolio"],
    summary="List trade history",
    description="Returns closed trade analytics records for the authenticated user.",
)
async def get_trade_history(
    user_id: str = Query(..., description="User identifier whose trade history should be returned."),
    limit: int = Query(default=100, ge=1, le=500, description="Maximum number of history rows to return."),
    request: Request = ...,
    container: ServiceContainer = Depends(get_container),
) -> dict:
    try:
        authenticated_user_id = get_user_id(request)
        _ensure_user_access(authenticated_user_id, user_id)
        analytics = getattr(container, "analytics_service", None)
        items = analytics.trade_history(user_id, limit=limit) if analytics is not None else []
        return {"count": len(items), "items": items}
    except AuthenticationError as exc:
        raise HTTPException(status_code=403, detail=exc.to_dict()) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/analytics/summary",
    tags=["User Portfolio"],
    summary="Get analytics summary",
    description="Returns win rate, drawdown, expectancy, and other core trading metrics for the authenticated user.",
)
async def get_analytics_summary(
    user_id: str = Query(..., description="User identifier whose analytics summary should be returned."),
    request: Request = ...,
    container: ServiceContainer = Depends(get_container),
) -> dict:
    try:
        authenticated_user_id = get_user_id(request)
        _ensure_user_access(authenticated_user_id, user_id)
        analytics = getattr(container, "analytics_service", None)
        return analytics.summary(user_id) if analytics is not None else {}
    except AuthenticationError as exc:
        raise HTTPException(status_code=403, detail=exc.to_dict()) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/analytics/performance",
    tags=["User Portfolio"],
    summary="Get analytics performance",
    description="Returns performance breakdowns, feedback-loop insights, and future-ready confluence weights for the authenticated user.",
)
async def get_analytics_performance(
    user_id: str = Query(..., description="User identifier whose analytics performance should be returned."),
    request: Request = ...,
    container: ServiceContainer = Depends(get_container),
) -> dict:
    try:
        authenticated_user_id = get_user_id(request)
        _ensure_user_access(authenticated_user_id, user_id)
        analytics = getattr(container, "analytics_service", None)
        return analytics.performance(user_id) if analytics is not None else {}
    except AuthenticationError as exc:
        raise HTTPException(status_code=403, detail=exc.to_dict()) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/trade/{trade_id}/timeline",
    response_model=TradeTimelineResponse,
    tags=["Trade Timeline"],
    summary="Get trade timeline",
    description="Returns a frontend-ready trade lifecycle timeline using cached active-trade and exchange-order state.",
)
async def get_trade_timeline(
    trade_id: str,
    request: Request,
    container: ServiceContainer = Depends(get_container),
) -> TradeTimelineResponse:
    try:
        authenticated_user_id = get_user_id(request)
        active_trade = container.redis_state_manager.load_active_trade(trade_id)
        order_payload = None
        if active_trade and active_trade.get("order_id"):
            order_payload = container.redis_state_manager.load_order(str(active_trade["order_id"]))
        if active_trade is None:
            for order in container.redis_state_manager.restore_orders():
                if order.get("trade_id") == trade_id:
                    order_payload = order
                    break
        if active_trade is None and order_payload is None:
            raise HTTPException(status_code=404, detail=f"Trade {trade_id} was not found in active cache state")
        owner_user_id = str(
            (active_trade or {}).get("user_id")
            or (order_payload or {}).get("user_id")
            or ""
        )
        if not owner_user_id:
            raise HTTPException(status_code=404, detail=f"Trade {trade_id} was not found in active cache state")
        _ensure_user_access(authenticated_user_id, owner_user_id)

        now = datetime.now(timezone.utc)
        events: list[TradeTimelineEvent] = []
        if active_trade:
            events.append(
                TradeTimelineEvent(
                    timestamp=now,
                    stage="SIGNAL_ACCEPTED",
                    status=str(active_trade.get("submitted_state", "ACCEPTED")),
                    description="Trade signal passed validation and entered the execution pipeline.",
                    metadata={
                        "symbol": str(active_trade.get("symbol", "")),
                        "side": str(active_trade.get("side", "")),
                        "expected_return": float(active_trade.get("expected_return", 0.0)),
                    },
                )
            )
            if active_trade.get("order_id"):
                events.append(
                    TradeTimelineEvent(
                        timestamp=now,
                        stage="ORDER_SUBMITTED",
                        status=str(active_trade.get("status", "SUBMITTED")),
                        description="An exchange order was submitted or restored from cache state.",
                        metadata={
                            "order_id": str(active_trade.get("order_id")),
                            "remaining_qty": float(active_trade.get("remaining_qty", 0.0)),
                            "execution_priority": str(active_trade.get("execution_priority", "")),
                        },
                    )
                )
            if active_trade.get("aggregate_order_id") or active_trade.get("virtual_order_id"):
                events.append(
                    TradeTimelineEvent(
                        timestamp=now,
                        stage="VIRTUAL_ALLOCATION",
                        status=str(active_trade.get("status", "ALLOCATED")),
                        description="This trade was allocated from an aggregated virtual parent order.",
                        metadata={
                            "aggregate_order_id": str(active_trade.get("aggregate_order_id", "")),
                            "virtual_order_id": str(active_trade.get("virtual_order_id", "")),
                        },
                    )
                )
        if order_payload:
            events.append(
                TradeTimelineEvent(
                    timestamp=now,
                    stage="ORDER_RECONCILIATION",
                    status=str(order_payload.get("status", "UNKNOWN")),
                    description="Latest cached exchange order state available for reconciliation.",
                    metadata={
                        "chain": str(order_payload.get("chain", "")),
                        "trade_id": str(order_payload.get("trade_id", trade_id)),
                    },
                )
            )

        return TradeTimelineResponse(
            trade_id=trade_id,
            current_status=str((active_trade or order_payload or {}).get("status", "UNKNOWN")),
            events=events,
        )
    except AuthenticationError as exc:
        raise HTTPException(status_code=403, detail=exc.to_dict()) from exc
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _ensure_user_access(authenticated_user_id: str, requested_user_id: str) -> None:
    if authenticated_user_id != requested_user_id:
        raise AuthenticationError(
            "Cannot access another user's data",
            error_code="UNAUTHORIZED_RESOURCE_ACCESS",
        )


def _load_viewer_signal_subscription(container: ServiceContainer, user_id: str) -> dict:
    payload = container.cache.get_json(f"subscription:{user_id}") or {}
    settings = getattr(container, "settings", None)
    default_balance = float(getattr(settings, "default_portfolio_balance", 0.0))
    return {
        "user_id": user_id,
        "tier": str(payload.get("tier", "free")),
        "balance": float(payload.get("balance", default_balance)),
        "risk_profile": str(payload.get("risk_profile", "moderate")),
    }


def _signal_visible_to_viewer(container: ServiceContainer, payload: dict, viewer_subscription: dict) -> bool:
    broadcaster = getattr(container, "signal_broadcaster", None)
    if broadcaster is None:
        return True
    eligible = broadcaster.filter_subscriptions(payload, [viewer_subscription])
    return bool(eligible)


def _batch_visible_to_user(payload: dict, user_id: str) -> bool:
    participant_ids = payload.get("participant_user_ids") or payload.get("user_ids") or []
    if isinstance(participant_ids, str):
        participant_ids = [participant_ids]
    normalized_participants = {str(item) for item in participant_ids if str(item).strip()}
    owner_user_id = str(payload.get("user_id", "")).strip()
    if owner_user_id:
        normalized_participants.add(owner_user_id)
    return user_id in normalized_participants

