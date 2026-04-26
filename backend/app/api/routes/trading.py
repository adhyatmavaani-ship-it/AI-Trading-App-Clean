from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.exceptions import (
    AuthenticationError,
    ExecutionError,
    RiskLimitExceededError,
    StateError,
    ValidationError,
)
from app.middleware.auth import can_execute_for_users, get_user_id
from app.schemas.trading import SignalResponse, TradeCloseRequest, TradeCloseResponse, TradeRequest, TradeResponse
from app.services.container import ServiceContainer, get_container

router = APIRouter(prefix="/trading", tags=["Trading"])


def _authorize_trade_user(http_request: Request, requested_user_id: str) -> tuple[str, str]:
    authenticated_user_id = get_user_id(http_request)
    normalized_requested_user_id = requested_user_id.strip()
    if normalized_requested_user_id == authenticated_user_id:
        return authenticated_user_id, normalized_requested_user_id
    if not can_execute_for_users(http_request):
        raise AuthenticationError(
            "Cannot execute trades for another user",
            error_code="UNAUTHORIZED_TRADE_EXECUTION",
        )
    execution_user_header = http_request.headers.get("X-Execution-User-Id", "").strip()
    if execution_user_header and execution_user_header != normalized_requested_user_id:
        raise AuthenticationError(
            "Execution user header does not match request.user_id",
            error_code="EXECUTION_USER_MISMATCH",
        )
    return authenticated_user_id, normalized_requested_user_id


@router.post("/evaluate/{symbol}", response_model=SignalResponse)
async def evaluate_symbol(
    symbol: str,
    request: Request,
    container: ServiceContainer = Depends(get_container),
) -> SignalResponse:
    """Evaluate a symbol for trading opportunity."""
    user_id = "unknown"
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    try:
        user_id = get_user_id(request)
        return await container.trading_orchestrator.evaluate_symbol(symbol.upper())
    except AuthenticationError as exc:
        raise HTTPException(status_code=403, detail=exc.to_dict()) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.to_dict()) from exc
    except Exception as exc:  # pragma: no cover
        await container.alerting_service.send(
            "Signal evaluation failed",
            f"Symbol={symbol.upper()} user={user_id} corr_id={correlation_id} error={exc}",
            severity="ERROR",
        )
        raise HTTPException(status_code=500, detail={
            "error_code": "EVALUATION_FAILED",
            "message": "Signal evaluation failed",
            "details": {"symbol": symbol.upper()}
        }) from exc


@router.post("/execute", response_model=TradeResponse)
async def execute_trade(
    request: TradeRequest,
    http_request: Request,
    container: ServiceContainer = Depends(get_container),
) -> TradeResponse:
    """Execute a trade signal."""
    user_id = "unknown"
    executor_user_id = "unknown"
    correlation_id = getattr(http_request.state, "correlation_id", "unknown")
    try:
        executor_user_id, user_id = _authorize_trade_user(http_request, request.user_id)
        # Validate required fields
        if not request.symbol:
            raise ValidationError("symbol is required", error_code="MISSING_SYMBOL")
        if not request.side or request.side.upper() not in ["BUY", "SELL"]:
            raise ValidationError("side must be BUY or SELL", error_code="INVALID_SIDE")
        if not request.quantity and not request.requested_notional:
            raise ValidationError("quantity or requested_notional required", error_code="MISSING_QUANTITY")

        return await container.trading_orchestrator.execute_signal(request)
    except AuthenticationError as exc:
        raise HTTPException(status_code=403, detail=exc.to_dict()) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.to_dict()) from exc
    except RiskLimitExceededError as exc:
        raise HTTPException(status_code=403, detail=exc.to_dict()) from exc
    except StateError as exc:
        raise HTTPException(status_code=409, detail=exc.to_dict()) from exc
    except Exception as exc:  # pragma: no cover
        await container.alerting_service.send(
            "Trade execution failed",
            f"Symbol={request.symbol} side={request.side} user={user_id} executor={executor_user_id} corr_id={correlation_id} error={exc}",
            severity="CRITICAL",
        )
        raise HTTPException(status_code=500, detail={
            "error_code": "EXECUTION_FAILED",
            "message": "Trade execution failed",
            "details": {"symbol": request.symbol}
        }) from exc


@router.post("/sniper/{symbol}", response_model=TradeResponse)
async def execute_sniper_trade(
    symbol: str,
    http_request: Request,
    container: ServiceContainer = Depends(get_container),
) -> TradeResponse:
    """Execute sniper trade (coordinated entry)."""
    user_id = "unknown"
    correlation_id = getattr(http_request.state, "correlation_id", "unknown")
    try:
        user_id = get_user_id(http_request)
        request = await container.dual_track_coordinator.build_trade_request(
            user_id=user_id,
            symbol=symbol.upper(),
        )
        if request is None:
            raise StateError(
                f"No sniper setup available for {symbol.upper()}",
                error_code="NO_SNIPER_SETUP",
                details={"symbol": symbol.upper()},
            )
        
        await container.dual_track_coordinator.warmup_execution_context(
            user_id=user_id,
            symbol=symbol.upper(),
        )
        return await container.trading_orchestrator.execute_signal(request)
    except AuthenticationError as exc:
        raise HTTPException(status_code=403, detail=exc.to_dict()) from exc
    except StateError as exc:
        raise HTTPException(status_code=409, detail=exc.to_dict()) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.to_dict()) from exc
    except Exception as exc:  # pragma: no cover
        await container.alerting_service.send(
            "Sniper execution failed",
            f"Symbol={symbol.upper()} user={user_id} corr_id={correlation_id} error={exc}",
            severity="CRITICAL",
        )
        raise HTTPException(status_code=500, detail={
            "error_code": "SNIPER_FAILED",
            "message": "Sniper execution failed",
            "details": {"symbol": symbol.upper()}
        }) from exc


@router.post("/close", response_model=TradeCloseResponse)
async def close_trade(
    close_request: TradeCloseRequest,
    http_request: Request,
    container: ServiceContainer = Depends(get_container),
) -> TradeCloseResponse:
    """Close an open trade position."""
    user_id = "unknown"
    correlation_id = getattr(http_request.state, "correlation_id", "unknown")
    try:
        user_id = get_user_id(http_request)
        # Permissions check
        if close_request.user_id != user_id:
            raise AuthenticationError(
                "Cannot close another user's trade",
                error_code="UNAUTHORIZED_CLOSE",
            )
        
        return container.trading_orchestrator.close_trade_position(
            user_id=close_request.user_id,
            trade_id=close_request.trade_id,
            exit_price=close_request.exit_price,
            closed_quantity=close_request.closed_quantity,
            exit_fee=close_request.exit_fee,
            reason=close_request.reason,
        )
    except AuthenticationError as exc:
        raise HTTPException(status_code=403, detail=exc.to_dict()) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.to_dict()) from exc
    except StateError as exc:
        raise HTTPException(status_code=409, detail=exc.to_dict()) from exc
    except Exception as exc:  # pragma: no cover
        await container.alerting_service.send(
            "Trade close failed",
            f"TradeID={close_request.trade_id} user={user_id} corr_id={correlation_id} error={exc}",
            severity="CRITICAL",
        )
        raise HTTPException(status_code=500, detail={
            "error_code": "CLOSE_FAILED",
            "message": "Trade close failed",
            "details": {"trade_id": close_request.trade_id}
        }) from exc
