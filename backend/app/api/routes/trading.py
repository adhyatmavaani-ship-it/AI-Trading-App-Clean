from datetime import datetime, timezone
import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.exceptions import (
    AuthenticationError,
    ExecutionError,
    RiskLimitExceededError,
    StateError,
    ValidationError,
)
from app.core.config import get_settings
from app.middleware.auth import can_execute_for_users, get_user_id
from app.schemas.trading import SignalResponse, TradeCloseRequest, TradeCloseResponse, TradeRequest, TradeResponse
from app.services.container import ServiceContainer, get_container
from app.services.risk_shield import RiskShieldBracket, RiskShieldService, UserRiskState

router = APIRouter(prefix="/trading", tags=["Trading"])
logger = logging.getLogger(__name__)


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


def _enforce_execution_circuit(container: ServiceContainer, request: TradeRequest) -> None:
    circuit_breaker = getattr(container, "execution_circuit_breaker", None)
    if circuit_breaker is None:
        return
    settings = getattr(container, "settings", get_settings())
    decision = circuit_breaker.evaluate(
        trading_mode=getattr(settings, "trading_mode", "paper"),
        symbol=request.symbol,
    )
    if decision.allowed:
        return
    raise StateError(
        "Execution temporarily paused while safety checks complete",
        error_code="EXECUTION_CIRCUIT_OPEN",
        details={
            "symbol": request.symbol.upper(),
            "side": request.side.upper(),
            "reasons": decision.reasons,
            "state": "execution temporarily paused",
            "details": decision.details,
        },
    )


def _idempotency_origin(http_request: Request) -> str:
    return (
        http_request.headers.get("X-Execution-Origin")
        or f"api:{http_request.url.path}"
    )


def _idempotency_key(http_request: Request) -> str | None:
    return http_request.headers.get("X-Idempotency-Key") or http_request.headers.get("Idempotency-Key")


def _mark_idempotency_unknown(container: ServiceContainer, claim, exc: Exception) -> None:
    idempotency_service = getattr(container, "execution_idempotency_service", None)
    if idempotency_service is not None and claim is not None:
        idempotency_service.mark_unknown_failure(claim, exc)


def _audit_execution_event(container: ServiceContainer, claim, event_type: str, payload: dict) -> None:
    if claim is None:
        return
    store = getattr(container, "pro_store", None)
    if store is None or not hasattr(store, "append_execution_audit_event"):
        return
    try:
        store.append_execution_audit_event(claim.execution_request_id, event_type, payload)
    except Exception:
        logger.warning(
            "execution_audit_write_failed",
            exc_info=True,
            extra={
                "event": "execution_audit_write_failed",
                "context": {"execution_request_id": claim.execution_request_id, "event_type": event_type},
            },
        )


def _shield_required(request: TradeRequest) -> bool:
    features = request.feature_snapshot or {}
    return bool(
        features.get("shield_required", 0.0) >= 1.0
        or features.get("paper_sandbox_request", 0.0) >= 1.0
    )


def _shield_bracket_from_request(request: TradeRequest) -> RiskShieldBracket:
    features = request.feature_snapshot or {}
    return RiskShieldBracket(
        entry_price=float(features.get("shield_entry_price", features.get("selected_price", 0.0)) or 0.0),
        stop_loss=float(features.get("shield_stop_loss", 0.0) or 0.0),
        take_profit=float(features.get("shield_take_profit", 0.0) or 0.0),
    )


def _cache_float(container: ServiceContainer, key: str, default: float = 0.0) -> float:
    cache = getattr(getattr(container, "micro_mode_controller", None), "cache", None)
    if cache is None or not hasattr(cache, "get"):
        return default
    try:
        return float(cache.get(key) or default)
    except Exception:
        return default


def _risk_state_for_request(container: ServiceContainer, request: TradeRequest) -> UserRiskState:
    settings = get_settings()
    summary = {}
    ledger = getattr(container, "portfolio_ledger", None)
    if ledger is not None and hasattr(ledger, "load_summary"):
        try:
            summary = ledger.load_summary(request.user_id) or {}
        except Exception:
            summary = {}
    features = request.feature_snapshot or {}
    balance = float(
        features.get(
            "shield_account_balance",
            summary.get("realized_equity", summary.get("starting_equity", settings.default_portfolio_balance)),
        )
        or settings.default_portfolio_balance
    )
    today = datetime.now(timezone.utc).date().isoformat()
    daily_pnl = float(
        features.get(
            "shield_daily_realized_pnl",
            _cache_float(container, f"micro:{request.user_id}:{today}:pnl", 0.0),
        )
        or 0.0
    )
    consecutive_losses = int(
        features.get(
            "shield_consecutive_losses",
            _cache_float(container, f"micro:{request.user_id}:consecutive_losses", 0.0),
        )
        or 0
    )
    closed_trades = int(features.get("shield_closed_trades", summary.get("closed_trades", 0)) or 0)
    winning_trades = int(features.get("shield_winning_trades", summary.get("winning_trades", 0)) or 0)
    avg_rr = float(features.get("shield_average_risk_reward", 0.0) or 0.0)
    return UserRiskState(
        account_balance=balance,
        daily_realized_pnl=daily_pnl,
        consecutive_losses=consecutive_losses,
        closed_trades=closed_trades,
        winning_trades=winning_trades,
        average_risk_reward=avg_rr,
    )


def _enforce_risk_shield(container: ServiceContainer, request: TradeRequest) -> None:
    if not _shield_required(request):
        return
    decision = RiskShieldService(get_settings()).evaluate_order(
        side=request.side,
        requested_notional=float(request.requested_notional or 0.0),
        bracket=_shield_bracket_from_request(request),
        user_state=_risk_state_for_request(container, request),
    )
    request.feature_snapshot.update(
        {
            "risk_shield_approved": 1.0 if decision.approved else 0.0,
            "risk_shield_auto_quantity": decision.auto_quantity,
            "risk_shield_max_notional": decision.max_notional,
            "risk_shield_risk_amount": decision.risk_amount,
            "risk_shield_risk_reward": decision.risk_reward,
            "risk_shield_daily_loss_pct": decision.daily_loss_pct,
            "risk_shield_live_unlocked": 1.0 if decision.live_unlocked else 0.0,
        }
    )
    if not decision.approved:
        raise RiskLimitExceededError(
            decision.reason,
            error_code=decision.reason_code,
            details={
                "symbol": request.symbol.upper(),
                "side": request.side.upper(),
                "auto_quantity": decision.auto_quantity,
                "max_notional": decision.max_notional,
                "risk_amount": decision.risk_amount,
                "risk_reward": decision.risk_reward,
                "daily_loss_pct": decision.daily_loss_pct,
                "locked_until": decision.locked_until,
                "license_status": decision.license_status,
                "live_unlocked": decision.live_unlocked,
            },
        )


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
    idempotency_claim = None
    try:
        executor_user_id, user_id = _authorize_trade_user(http_request, request.user_id)
        # Validate required fields
        if not request.symbol:
            raise ValidationError("symbol is required", error_code="MISSING_SYMBOL")
        if not request.side or request.side.upper() not in ["BUY", "SELL"]:
            raise ValidationError("side must be BUY or SELL", error_code="INVALID_SIDE")
        if not request.quantity and not request.requested_notional:
            raise ValidationError("quantity or requested_notional required", error_code="MISSING_QUANTITY")

        idempotency_service = getattr(container, "execution_idempotency_service", None)
        if idempotency_service is not None:
            idempotency_claim = idempotency_service.peek_replay(
                request,
                idempotency_key=_idempotency_key(http_request),
                origin=_idempotency_origin(http_request),
            )
            request = idempotency_claim.request
            if idempotency_claim.replay_response is not None:
                return idempotency_claim.replay_response

        try:
            _enforce_risk_shield(container, request)
            _audit_execution_event(
                container,
                idempotency_claim,
                "risk_shield_decision",
                {"approved": True, "symbol": request.symbol.upper(), "side": request.side.upper()},
            )
        except RiskLimitExceededError as exc:
            _audit_execution_event(
                container,
                idempotency_claim,
                "risk_shield_decision",
                {
                    "approved": False,
                    "symbol": request.symbol.upper(),
                    "side": request.side.upper(),
                    "error_code": exc.error_code,
                    "reason": str(exc),
                },
            )
            raise
        _enforce_execution_circuit(container, request)
        if idempotency_service is not None:
            idempotency_claim = idempotency_service.claim(
                request,
                idempotency_key=_idempotency_key(http_request),
                origin=_idempotency_origin(http_request),
                trading_mode=getattr(getattr(container, "settings", get_settings()), "trading_mode", "paper"),
            )
            request = idempotency_claim.request
            if idempotency_claim.replay_response is not None:
                return idempotency_claim.replay_response
            idempotency_service.mark_validated(idempotency_claim)
            idempotency_service.mark_submitted(idempotency_claim)
        response = await container.trading_orchestrator.execute_signal(request)
        if idempotency_service is not None and idempotency_claim is not None:
            idempotency_service.complete(idempotency_claim, response)
        return response
    except AuthenticationError as exc:
        detail = exc.to_dict()
        details = dict(detail.get("details") or {})
        details.setdefault("correlation_id", correlation_id)
        detail["details"] = details
        raise HTTPException(status_code=403, detail=detail) from exc
    except ValidationError as exc:
        _mark_idempotency_unknown(container, idempotency_claim, exc)
        raise _http_exception_from_trading_error(exc, correlation_id=correlation_id) from exc
    except RiskLimitExceededError as exc:
        _mark_idempotency_unknown(container, idempotency_claim, exc)
        raise _http_exception_from_trading_error(exc, correlation_id=correlation_id) from exc
    except ValueError as exc:
        _mark_idempotency_unknown(container, idempotency_claim, exc)
        mapped = _map_execution_value_error(exc, request=request, correlation_id=correlation_id)
        raise _http_exception_from_trading_error(mapped, correlation_id=correlation_id) from exc
    except ExecutionError as exc:
        _mark_idempotency_unknown(container, idempotency_claim, exc)
        raise _http_exception_from_trading_error(exc, correlation_id=correlation_id) from exc
    except RuntimeError as exc:
        _mark_idempotency_unknown(container, idempotency_claim, exc)
        mapped = _map_execution_runtime_error(exc, request=request, correlation_id=correlation_id)
        raise _http_exception_from_trading_error(mapped, correlation_id=correlation_id) from exc
    except StateError as exc:
        _mark_idempotency_unknown(container, idempotency_claim, exc)
        raise _http_exception_from_trading_error(exc, correlation_id=correlation_id) from exc
    except Exception as exc:  # pragma: no cover
        _mark_idempotency_unknown(container, idempotency_claim, exc)
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
    idempotency_claim = None
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
        try:
            _enforce_risk_shield(container, request)
            _audit_execution_event(
                container,
                idempotency_claim,
                "risk_shield_decision",
                {"approved": True, "symbol": request.symbol.upper(), "side": request.side.upper()},
            )
        except RiskLimitExceededError as exc:
            _audit_execution_event(
                container,
                idempotency_claim,
                "risk_shield_decision",
                {
                    "approved": False,
                    "symbol": request.symbol.upper(),
                    "side": request.side.upper(),
                    "error_code": exc.error_code,
                    "reason": str(exc),
                },
            )
            raise
        _enforce_execution_circuit(container, request)
        idempotency_service = getattr(container, "execution_idempotency_service", None)
        if idempotency_service is not None:
            idempotency_claim = idempotency_service.claim(
                request,
                idempotency_key=_idempotency_key(http_request),
                origin=_idempotency_origin(http_request),
                trading_mode=getattr(getattr(container, "settings", get_settings()), "trading_mode", "paper"),
            )
            request = idempotency_claim.request
            if idempotency_claim.replay_response is not None:
                return idempotency_claim.replay_response
            idempotency_service.mark_validated(idempotency_claim)
            idempotency_service.mark_submitted(idempotency_claim)
        response = await container.trading_orchestrator.execute_signal(request)
        if idempotency_service is not None and idempotency_claim is not None:
            idempotency_service.complete(idempotency_claim, response)
        return response
    except AuthenticationError as exc:
        raise HTTPException(status_code=403, detail=exc.to_dict()) from exc
    except StateError as exc:
        _mark_idempotency_unknown(container, idempotency_claim, exc)
        raise HTTPException(status_code=409, detail=exc.to_dict()) from exc
    except ValidationError as exc:
        _mark_idempotency_unknown(container, idempotency_claim, exc)
        raise HTTPException(status_code=400, detail=exc.to_dict()) from exc
    except Exception as exc:  # pragma: no cover
        _mark_idempotency_unknown(container, idempotency_claim, exc)
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
