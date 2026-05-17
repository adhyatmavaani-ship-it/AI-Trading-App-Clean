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


def _http_exception_from_trading_error(exc, *, correlation_id: str) -> HTTPException:
    detail = exc.to_dict()
    details = dict(detail.get("details") or {})
    details.setdefault("correlation_id", correlation_id)
    detail["details"] = details
    return HTTPException(status_code=exc.status_code, detail=detail)


def _map_execution_value_error(exc: ValueError, *, request: TradeRequest, correlation_id: str):
    message = str(exc).strip() or "Trade execution validation failed"
    normalized = message.lower()
    details = {
        "symbol": request.symbol.upper(),
        "side": request.side.upper(),
        "correlation_id": correlation_id,
    }

    if message == "quantity or requested_notional is required":
        return ValidationError(message, error_code="MISSING_EXECUTION_SIZE", details=details)
    if message == "limit_price is required for LIMIT orders":
        return ValidationError(message, error_code="MISSING_LIMIT_PRICE", details=details)
    if message == "Trading is paused by drawdown protection":
        return StateError(message, error_code="DRAWDOWN_PAUSE_ACTIVE", details=details)
    if message.startswith("Trading is paused by emergency stop:"):
        details["stop_reason"] = message.split(":", 1)[1].strip() or "manual"
        return StateError(message, error_code="EMERGENCY_STOP_ACTIVE", details=details)
    if message == "Trading is paused because execution latency is degraded":
        return StateError(message, error_code="EXECUTION_DEGRADED", details=details)
    if message == "Trade confidence is below the strict execution floor":
        details["confidence"] = float(request.confidence)
        details["required_confidence"] = float(
            request.feature_snapshot.get(
                "paper_trade_confidence_floor",
                request.feature_snapshot.get("strict_trade_confidence", request.confidence),
            )
            or request.confidence
        )
        return RiskLimitExceededError(message, error_code="CONFIDENCE_TOO_LOW", details=details)
    if message.startswith("Risk profile ") and " blocks " in message:
        details["symbol"] = request.symbol.upper()
        return RiskLimitExceededError(message, error_code="SYMBOL_NOT_ALLOWED", details=details)
    if message == "Security scanner blocked trade":
        return ValidationError(message, error_code="SYMBOL_NOT_TRADABLE", details=details)
    if message == "Whale tracker vetoed conflicting trade":
        return RiskLimitExceededError(message, error_code="WHALE_CONFLICT_VETO", details=details)
    if message == "Capital protection disabled trading":
        return StateError(message, error_code="CAPITAL_PROTECTION_DISABLED", details=details)
    if normalized.startswith("trade probability ") and " below threshold " in normalized:
        return RiskLimitExceededError(message, error_code="TRADE_PROBABILITY_TOO_LOW", details=details)
    if message.startswith("Strict trade gate rejected trade:"):
        details["strict_trade_reason"] = message.split(":", 1)[1].strip()
        return RiskLimitExceededError(message, error_code="STRICT_GATE_BLOCKED", details=details)
    if message.startswith("Meta controller blocked trade:"):
        raw_reasons = message.split(":", 1)[1].strip()
        details["reasons"] = [item.strip() for item in raw_reasons.split(",") if item.strip()]
        return RiskLimitExceededError(message, error_code="META_CONTROLLER_BLOCKED", details=details)
    if message.startswith("Micro mode rejected trade:"):
        raw_reasons = message.split(":", 1)[1].strip()
        reasons = [item.strip() for item in raw_reasons.split(",") if item.strip()]
        details["reasons"] = reasons
        if "loss_cooldown" in reasons:
            return RiskLimitExceededError(message, error_code="COOLDOWN_ACTIVE", details=details)
        if "slippage_too_high" in reasons:
            return RiskLimitExceededError(message, error_code="SLIPPAGE_UNSAFE", details=details)
        if "daily_loss_limit" in reasons:
            return RiskLimitExceededError(message, error_code="DAILY_LOSS_LIMIT_REACHED", details=details)
        return RiskLimitExceededError(message, error_code="MICRO_MODE_BLOCKED", details=details)
    if message == "below_exchange_minimum":
        return ValidationError("Order size is below exchange minimum", error_code="MIN_NOTIONAL_NOT_MET", details=details)
    if message == "User protection controls reduced trade allocation to zero":
        return RiskLimitExceededError(message, error_code="INSUFFICIENT_ALLOCATABLE_BALANCE", details=details)
    if "portfolio exposure limit reached" in normalized:
        return RiskLimitExceededError(message, error_code="EXPOSURE_EXCEEDED", details=details)
    if "portfolio side exposure limit reached" in normalized:
        return RiskLimitExceededError(message, error_code="SIDE_EXPOSURE_EXCEEDED", details=details)
    if "portfolio theme exposure limit reached" in normalized:
        return RiskLimitExceededError(message, error_code="THEME_EXPOSURE_EXCEEDED", details=details)
    if "portfolio cluster exposure limit reached" in normalized:
        return RiskLimitExceededError(message, error_code="CLUSTER_EXPOSURE_EXCEEDED", details=details)
    if "portfolio beta bucket exposure limit reached" in normalized:
        return RiskLimitExceededError(message, error_code="BETA_BUCKET_EXCEEDED", details=details)
    if "portfolio concentration limit reached" in normalized:
        return RiskLimitExceededError(message, error_code="PORTFOLIO_CONCENTRATION_LIMIT", details=details)
    if "portfolio controls reduced trade below minimum notional" in normalized:
        return ValidationError(message, error_code="MIN_NOTIONAL_NOT_MET", details=details)
    if "daily loss limit reached" in normalized:
        return RiskLimitExceededError(message, error_code="DAILY_LOSS_LIMIT_REACHED", details=details)
    if "emergency stop is active" in normalized:
        return StateError(message, error_code="EMERGENCY_STOP_ACTIVE", details=details)
    if "requested limit price exceeds slippage guardrail" in normalized:
        return RiskLimitExceededError(message, error_code="SLIPPAGE_UNSAFE", details=details)
    if "order does not satisfy exchange minimum notional" in normalized:
        return ValidationError(message, error_code="MIN_NOTIONAL_NOT_MET", details=details)
    if message.startswith("Trade safety validation failed:"):
        raw_reasons = message.split(":", 1)[1].strip()
        details["reasons"] = [item.strip() for item in raw_reasons.split(",") if item.strip()]
        if "slippage" in normalized:
            return RiskLimitExceededError(message, error_code="SLIPPAGE_UNSAFE", details=details)
        if "volatility" in normalized:
            return RiskLimitExceededError(message, error_code="VOLATILITY_TOO_HIGH", details=details)
        if "liquidity coverage" in normalized:
            return RiskLimitExceededError(message, error_code="LIQUIDITY_INSUFFICIENT", details=details)
        return RiskLimitExceededError(message, error_code="TRADE_SAFETY_REJECTED", details=details)
    return ValidationError(message, error_code="EXECUTION_VALIDATION_FAILED", details=details)


def _map_execution_runtime_error(exc: RuntimeError, *, request: TradeRequest, correlation_id: str):
    message = str(exc).strip() or "Execution service is unavailable"
    details = {
        "symbol": request.symbol.upper(),
        "side": request.side.upper(),
        "correlation_id": correlation_id,
    }
    normalized = message.lower()
    if "live execution is unavailable" in normalized or "no exchange clients available" in normalized:
        return ExecutionError(message, error_code="BROKER_UNAVAILABLE", details=details)
    if "not initialized" in normalized:
        return ExecutionError(message, error_code="BROKER_UNAVAILABLE", details=details)
    return ExecutionError(message, error_code="EXECUTION_RUNTIME_ERROR", details=details)


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
        detail = exc.to_dict()
        details = dict(detail.get("details") or {})
        details.setdefault("correlation_id", correlation_id)
        detail["details"] = details
        raise HTTPException(status_code=403, detail=detail) from exc
    except ValidationError as exc:
        raise _http_exception_from_trading_error(exc, correlation_id=correlation_id) from exc
    except ValueError as exc:
        mapped = _map_execution_value_error(exc, request=request, correlation_id=correlation_id)
        raise _http_exception_from_trading_error(mapped, correlation_id=correlation_id) from exc
    except RiskLimitExceededError as exc:
        raise _http_exception_from_trading_error(exc, correlation_id=correlation_id) from exc
    except ExecutionError as exc:
        raise _http_exception_from_trading_error(exc, correlation_id=correlation_id) from exc
    except RuntimeError as exc:
        mapped = _map_execution_runtime_error(exc, request=request, correlation_id=correlation_id)
        raise _http_exception_from_trading_error(mapped, correlation_id=correlation_id) from exc
    except StateError as exc:
        raise _http_exception_from_trading_error(exc, correlation_id=correlation_id) from exc
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
