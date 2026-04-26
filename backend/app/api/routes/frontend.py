from __future__ import annotations

from datetime import datetime, timezone

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
from app.services.container import ServiceContainer, get_container

router = APIRouter()


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
        authenticated_user_id = get_user_id(request)
        viewer_subscription = _load_viewer_signal_subscription(container, authenticated_user_id)
        signals = await _collect_live_signals(container, viewer_subscription)
        if not signals:
            await _generate_live_signals(container)
            signals = await _collect_live_signals(container, viewer_subscription)
        ordered = sorted(signals, key=lambda item: item.published_at, reverse=True)[:limit]
        return LiveSignalsResponse(count=len(ordered), items=ordered)
    except AuthenticationError as exc:
        raise HTTPException(status_code=403, detail=exc.to_dict()) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


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


async def _generate_live_signals(container: ServiceContainer) -> None:
    symbols = list(container.settings.websocket_symbols or ["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    limit = max(1, int(container.settings.signal_force_min_candidates))
    for symbol in symbols[: max(limit, min(5, len(symbols)))]:
        try:
            await container.trading_orchestrator.evaluate_symbol(symbol.upper())
        except Exception:
            continue


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
    return {
        "user_id": user_id,
        "tier": str(payload.get("tier", "free")),
        "balance": float(payload.get("balance", container.settings.default_portfolio_balance)),
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

