from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
import time

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
from app.services.chart_intelligence import (
    ASSISTANT_MODES,
    build_chart_intelligence,
    resample_ohlcv,
)
from app.services.container import ServiceContainer, get_container

router = APIRouter()
logger = logging.getLogger(__name__)


class MockPriceMoveRequest(BaseModel):
    symbol: str = Field(..., min_length=1, description="Symbol whose cached market data should be shifted.")
    change: float = Field(..., description="Relative price change to inject. Example: -0.02 for a 2 percent drop.")
    user_id: str | None = Field(default=None, description="Optional user whose active trades should be inspected.")
    volume_multiplier: float = Field(default=3.0, ge=1.0, description="How aggressively the last candle volume should be amplified.")
    run_monitor: bool = Field(default=True, description="Whether to run the active trade monitor immediately after the move.")


class MarketSummaryRequest(BaseModel):
    limit: int = Field(default=18, ge=6, le=50, description="How many symbols should be included in the market sentiment scan.")


class AssistantModeRequest(BaseModel):
    mode: str = Field(..., description="Requested trade assistant mode.")


def _ensure_debug_routes_enabled(container: ServiceContainer) -> None:
    settings = getattr(container, "settings", None)
    if settings is not None and not bool(settings.effective_debug_routes_enabled):
        raise HTTPException(status_code=404, detail="Not Found")


@router.get(
    "/diag/exchange",
    tags=["Diagnostics"],
    summary="Get exchange and market-data diagnostics",
    description="Returns configured exchange state, retry status, current market-data mode, and a live probe showing whether exchange or simulated data is being used.",
)
async def get_exchange_diagnostics(
    sample_symbol: str = Query(default="BTCUSDT", description="Symbol to probe for exchange diagnostics."),
    request: Request = ...,
    container: ServiceContainer = Depends(get_container),
) -> dict:
    try:
        _ensure_debug_routes_enabled(container)
        get_user_id(request)
        market_data = container.market_data
        diagnostics = market_data.diagnostics() if hasattr(market_data, "diagnostics") else {}
        normalized_symbol = str(sample_symbol or "BTCUSDT").upper().strip()
        probe: dict[str, object] = {"symbol": normalized_symbol}
        try:
            latest_price = await market_data.fetch_latest_price(normalized_symbol)
            order_book = await market_data.fetch_order_book(normalized_symbol)
            frames = await market_data.fetch_multi_timeframe_ohlcv(normalized_symbol, intervals=("1m", "5m", "15m"))
            probe.update(
                {
                    "latest_price": float(latest_price),
                    "best_bid": float(order_book.get("bids", [{}])[0].get("price", 0.0)) if order_book.get("bids") else 0.0,
                    "best_ask": float(order_book.get("asks", [{}])[0].get("price", 0.0)) if order_book.get("asks") else 0.0,
                    "ohlcv_rows": {interval: int(len(frame)) for interval, frame in frames.items()},
                    "last_fetch_details": {
                        key: value
                        for key, value in diagnostics.get("last_fetch_details", {}).items()
                        if key.startswith(f"price:{normalized_symbol}")
                        or key.startswith(f"order_book:{normalized_symbol}")
                        or key.startswith(f"ohlcv:{normalized_symbol}")
                    },
                }
            )
        except Exception as exc:
            probe["error"] = str(exc)
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "market_data": diagnostics,
            "probe": probe,
        }
    except AuthenticationError as exc:
        raise HTTPException(status_code=403, detail=exc.to_dict()) from exc
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


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
    started = time.perf_counter()
    settings = getattr(container, "settings", None)
    timeout_seconds = max(float(getattr(settings, "live_signals_route_timeout_seconds", 2.5)), 0.1)
    slow_threshold = max(float(getattr(settings, "slow_operation_threshold_seconds", 1.0)), 0.1)
    response_cache_ttl_seconds = max(int(getattr(settings, "live_signals_response_cache_ttl_seconds", 3)), 0)
    auth_user_id = "anonymous"
    cache_hit = False
    used_generated = False
    try:
        try:
            auth_user_id = get_user_id(request)
        except AuthenticationError:
            auth_user_id = "anonymous"
        viewer_subscription = _load_viewer_signal_subscription(container, auth_user_id)
        cache_key = _live_signals_response_cache_key(viewer_subscription, limit)
        cached_response = _cache_get_json_safe(container, cache_key)
        if cached_response:
            cache_hit = True
            return LiveSignalsResponse(**cached_response)

        target = min(limit, 3)
        cached_signals = sorted(
            await _collect_live_signals(container, viewer_subscription),
            key=lambda item: item.published_at,
            reverse=True,
        )
        signals = list(cached_signals[:limit])
        if len(signals) < target:
            try:
                async with asyncio.timeout(timeout_seconds):
                    generated = await _generate_live_signals(container, limit=target)
                if generated:
                    used_generated = True
                seen_ids = {item.signal_id for item in signals}
                signals.extend(item for item in generated if item.signal_id not in seen_ids)
            except TimeoutError:
                logger.warning(
                    "live_signals_generation_timed_out",
                    extra={
                        "event": "live_signals_generation_timed_out",
                        "context": {
                            "timeout_seconds": timeout_seconds,
                            "user_id": auth_user_id,
                        },
                    },
                )
            except asyncio.CancelledError:
                logger.warning(
                    "live_signals_generation_cancelled",
                    extra={
                        "event": "live_signals_generation_cancelled",
                        "context": {"user_id": auth_user_id},
                    },
                )
                raise
            except Exception as exc:
                logger.exception(
                    "live_signals_generation_failed",
                    extra={
                        "event": "live_signals_generation_failed",
                        "context": {
                            "user_id": auth_user_id,
                            "error": str(exc)[:200],
                        },
                    },
                )
        if not signals:
            signals = _fallback_live_signals(container, limit=target)
        ordered = sorted(signals, key=lambda item: item.published_at, reverse=True)[:limit]
        response = LiveSignalsResponse(count=len(ordered), items=ordered)
        if response_cache_ttl_seconds > 0:
            _cache_set_json_safe(
                container,
                cache_key,
                response.model_dump(mode="json"),
                ttl=response_cache_ttl_seconds,
            )
        return response
    except AuthenticationError as exc:
        raise HTTPException(status_code=403, detail=exc.to_dict()) from exc
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        _log_route_timing(
            path="/v1/signals/live",
            started=started,
            slow_threshold=slow_threshold,
            context={
                "cache_hit": cache_hit,
                "used_generated": used_generated,
                "user_id": auth_user_id,
            },
        )


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


@router.get(
    "/market/candles",
    tags=["Market"],
    summary="Get live market candles for chart rendering",
    description="Returns cached or exchange-backed OHLCV candles plus AI trade markers so the Flutter chart can render a TradingView-style market panel.",
)
async def get_market_candles(
    symbol: str = Query(default="BTCUSDT", description="Market symbol to chart."),
    interval: str = Query(default="5m", pattern=r"^(1m|3m|5m|15m|1h)$", description="Candle interval to return."),
    limit: int = Query(default=96, ge=16, le=240, description="Maximum number of candles to return."),
    user_id: str | None = Query(default=None, description="Optional user whose AI trade markers should be included."),
    request: Request = ...,
    container: ServiceContainer = Depends(get_container),
) -> dict:
    try:
        authenticated_user_id = get_user_id(request)
        target_user_id = str(user_id or authenticated_user_id).strip()
        _ensure_user_access(authenticated_user_id, target_user_id)
        return await _build_market_chart_payload(
            container=container,
            authenticated_user_id=authenticated_user_id,
            target_user_id=target_user_id,
            symbol=symbol,
            interval=interval,
            limit=limit,
        )
    except AuthenticationError as exc:
        raise HTTPException(status_code=403, detail=exc.to_dict()) from exc
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/market/opportunity/{symbol}",
    tags=["Market"],
    summary="Get AI opportunity snapshot for one symbol",
    description="Returns scalp scoring, regime, overlays, strategy telemetry, and execution guidance without requiring the full chart payload.",
)
async def get_market_opportunity(
    symbol: str,
    interval: str = Query(default="5m", pattern=r"^(1m|3m|5m|15m|1h)$", description="Scalp interval to evaluate."),
    user_id: str | None = Query(default=None, description="Optional user whose assistant mode should be used."),
    request: Request = ...,
    container: ServiceContainer = Depends(get_container),
) -> dict:
    try:
        authenticated_user_id = get_user_id(request)
        target_user_id = str(user_id or authenticated_user_id).strip()
        _ensure_user_access(authenticated_user_id, target_user_id)
        payload = await _build_market_chart_payload(
            container=container,
            authenticated_user_id=authenticated_user_id,
            target_user_id=target_user_id,
            symbol=symbol,
            interval=interval,
            limit=96,
        )
        return {
            "symbol": payload["symbol"],
            "interval": payload["interval"],
            "chart_engine": payload["chart_engine"],
            "scalp_engine": payload["scalp_engine"],
            "opportunity": payload["opportunity"],
            "market_regime": payload["market_regime"],
            "assistant_modes": payload["assistant_modes"],
            "active_assistant_mode": payload["active_assistant_mode"],
            "execution_guide": payload["execution_guide"],
            "strategy_state": payload["strategy_state"],
            "ai_feed": payload["ai_feed"],
            "overlays": payload["overlays"],
            "render_hints": payload["render_hints"],
        }
    except AuthenticationError as exc:
        raise HTTPException(status_code=403, detail=exc.to_dict()) from exc
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/market/assistant-mode",
    tags=["Market"],
    summary="Get current AI trade assistant mode",
    description="Returns the active assistant mode for the authenticated user plus the supported Manual, Assisted, Semi Auto, and Full Auto modes.",
)
async def get_market_assistant_mode(
    request: Request = ...,
    container: ServiceContainer = Depends(get_container),
) -> dict:
    try:
        user_id = get_user_id(request)
        return {
            "user_id": user_id,
            "mode": _load_assistant_mode(container, user_id),
            "modes": list(ASSISTANT_MODES),
        }
    except AuthenticationError as exc:
        raise HTTPException(status_code=403, detail=exc.to_dict()) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/market/assistant-mode",
    tags=["Market"],
    summary="Update current AI trade assistant mode",
    description="Stores the authenticated user's preferred assistant mode while preserving the existing backend execution architecture.",
)
async def set_market_assistant_mode(
    payload: AssistantModeRequest,
    request: Request = ...,
    container: ServiceContainer = Depends(get_container),
) -> dict:
    try:
        user_id = get_user_id(request)
        normalized_mode = _normalize_assistant_mode(payload.mode)
        container.cache.set_json(
            _assistant_mode_cache_key(user_id),
            {"mode": normalized_mode},
            ttl=max(int(getattr(container.settings, "signal_version_ttl_seconds", 3600)), 60),
        )
        return {
            "user_id": user_id,
            "mode": normalized_mode,
            "modes": list(ASSISTANT_MODES),
        }
    except AuthenticationError as exc:
        raise HTTPException(status_code=403, detail=exc.to_dict()) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/market/universe",
    tags=["Market"],
    summary="Get tradable market universe snapshot",
    description="Returns top liquid symbols and derived categories like top gainers, high volatility, and AI picks for the frontend market board.",
)
async def get_market_universe(
    limit: int = Query(default=18, ge=6, le=50, description="Maximum number of symbols to scan."),
    request: Request = ...,
    container: ServiceContainer = Depends(get_container),
) -> dict:
    try:
        get_user_id(request)
        scanner = getattr(container, "market_universe_scanner", None)
        if scanner is None:
            return {"count": 0, "items": [], "categories": {}}
        return await scanner.snapshot(limit=limit)
    except AuthenticationError as exc:
        raise HTTPException(status_code=403, detail=exc.to_dict()) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def _build_market_chart_payload(
    *,
    container: ServiceContainer,
    authenticated_user_id: str,
    target_user_id: str,
    symbol: str,
    interval: str,
    limit: int,
) -> dict:
    _ensure_user_access(authenticated_user_id, target_user_id)
    normalized_symbol = str(symbol or "BTCUSDT").upper().strip()
    normalized_interval = str(interval or "5m").lower().strip()
    assistant_mode = _load_assistant_mode(container, target_user_id)
    cache_ttl_seconds = max(int(getattr(container.settings, "market_chart_cache_ttl_seconds", 2)), 0)
    cache_key = (
        f"market:chart:v2:{target_user_id}:{normalized_symbol}:{normalized_interval}:"
        f"{min(max(int(limit), 16), 240)}:{assistant_mode}"
    )
    cached = container.cache.get_json(cache_key)
    if cached:
        return cached

    frame = await _fetch_chart_frame(
        container=container,
        symbol=normalized_symbol,
        interval=normalized_interval,
    )
    if frame is None or getattr(frame, "empty", True):
        payload = {
            "symbol": normalized_symbol,
            "interval": normalized_interval,
            "candles": [],
            "markers": [],
            "confidence_intervals": [],
            "confidence_history": [],
            "latest_price": 0.0,
            "change_pct": 0.0,
            **build_chart_intelligence(
                symbol=normalized_symbol,
                interval=normalized_interval,
                frame=None,
                assistant_mode=assistant_mode,
            ),
        }
        payload.update(_snapshot_integrity(payload))
        if cache_ttl_seconds > 0:
            container.cache.set_json(cache_key, payload, ttl=cache_ttl_seconds)
        return payload

    trimmed = frame.tail(limit).copy()
    for column in ("open", "high", "low", "close", "volume"):
        trimmed[column] = trimmed[column].astype(float)
    latest_price = float(trimmed["close"].iloc[-1])
    previous_price = float(trimmed["close"].iloc[-2] if len(trimmed) > 1 else latest_price)
    change_pct = ((latest_price / max(previous_price, 1e-8)) - 1.0) * 100.0
    candles = [
        {
            "timestamp": int(row.get("close_time", row.get("open_time", 0)) or 0),
            "open": round(float(row["open"]), 8),
            "high": round(float(row["high"]), 8),
            "low": round(float(row["low"]), 8),
            "close": round(float(row["close"]), 8),
            "volume": round(float(row["volume"]), 8),
        }
        for row in trimmed.to_dict(orient="records")
    ]
    markers = _build_market_markers(
        container=container,
        target_user_id=target_user_id,
        normalized_symbol=normalized_symbol,
        candles=candles,
        latest_price=latest_price,
    )
    signal = await _load_chart_signal(container, normalized_symbol)
    analytics = getattr(container, "analytics_service", None)
    intelligence = build_chart_intelligence(
        symbol=normalized_symbol,
        interval=normalized_interval,
        frame=trimmed,
        signal=signal,
        existing_markers=markers,
        analytics_summary=analytics.summary(target_user_id) if analytics is not None else None,
        assistant_mode=assistant_mode,
        learning_enabled=getattr(container, "adaptive_learning_service", None) is not None,
    )
    markers = _dedupe_market_markers([*markers, *list(intelligence.pop("synthetic_markers", []))])
    confidence_intervals = _build_confidence_intervals(
        candles=candles,
        markers=markers,
    )
    activity_engine = getattr(container, "user_experience_engine", None)
    confidence_history = (
        activity_engine.confidence_history(symbol=normalized_symbol, limit=24)
        if activity_engine is not None
        else []
    )
    payload = {
        "symbol": normalized_symbol,
        "interval": normalized_interval,
        "latest_price": round(latest_price, 8),
        "change_pct": round(change_pct, 4),
        "candles": candles,
        "markers": markers,
        "confidence_intervals": confidence_intervals,
        "confidence_history": confidence_history,
        **intelligence,
    }
    payload.update(_snapshot_integrity(payload))
    if cache_ttl_seconds > 0:
        container.cache.set_json(cache_key, payload, ttl=cache_ttl_seconds)
    return payload


def _snapshot_integrity(payload: dict) -> dict[str, object]:
    stable = {
        key: value
        for key, value in payload.items()
        if key not in {"snapshot_version", "state_hash", "integrity_checksum"}
    }
    encoded = json.dumps(stable, sort_keys=True, default=str)
    state_hash = hashlib.sha1(encoded.encode("utf-8")).hexdigest()[:16]
    snapshot_version = int(datetime.now(timezone.utc).timestamp() * 1000)
    checksum = hashlib.sha256(
        f"market_chart:{snapshot_version}:{state_hash}".encode("utf-8")
    ).hexdigest()[:24]
    return {
        "snapshot_version": snapshot_version,
        "state_hash": state_hash,
        "integrity_checksum": checksum,
    }


async def _fetch_chart_frame(
    *,
    container: ServiceContainer,
    symbol: str,
    interval: str,
):
    normalized_interval = str(interval or "5m").lower().strip()
    if normalized_interval == "3m":
        frames = await container.market_data.fetch_multi_timeframe_ohlcv(
            symbol,
            intervals=("1m",),
        )
        return resample_ohlcv(frames.get("1m"), minutes=3)
    frames = await container.market_data.fetch_multi_timeframe_ohlcv(
        symbol,
        intervals=(normalized_interval,),
    )
    return frames.get(normalized_interval)


async def _load_chart_signal(
    container: ServiceContainer,
    symbol: str,
) -> SignalResponse | None:
    orchestrator = getattr(container, "trading_orchestrator", None)
    if orchestrator is None or not hasattr(orchestrator, "evaluate_symbol"):
        return None
    try:
        return await orchestrator.evaluate_symbol(symbol)
    except Exception:
        return None


def _assistant_mode_cache_key(user_id: str) -> str:
    return f"market:assistant_mode:{str(user_id or 'system').strip().lower() or 'system'}"


def _normalize_assistant_mode(mode: str) -> str:
    normalized = str(mode or "").strip().upper().replace(" ", "_")
    if normalized not in ASSISTANT_MODES:
        raise ValueError("mode must be one of MANUAL, ASSISTED, SEMI_AUTO, FULL_AUTO")
    return normalized


def _load_assistant_mode(container: ServiceContainer, user_id: str) -> str:
    payload = container.cache.get_json(_assistant_mode_cache_key(user_id)) or {}
    candidate = str(payload.get("mode", "ASSISTED") or "ASSISTED").upper()
    return candidate if candidate in ASSISTANT_MODES else "ASSISTED"


async def _market_summary_response(
    *,
    request: Request,
    container: ServiceContainer,
    limit: int,
) -> dict:
    get_user_id(request)
    scanner = getattr(container, "market_universe_scanner", None)
    if scanner is None:
        return {
            "sentiment_score": 0.0,
            "sentiment_label": "NEUTRAL",
            "market_breadth": 0.0,
            "avg_change_pct": 0.0,
            "avg_volatility_pct": 0.0,
            "participation_score": 0.0,
            "confidence_score": 0.0,
            "ticker": [],
            "heatmap": [],
            "top_movers": [],
            "confidence_history": [],
        }
    summary = await scanner.summary(limit=limit)
    activity_engine = getattr(container, "user_experience_engine", None)
    summary["confidence_history"] = (
        activity_engine.confidence_history(limit=24) if activity_engine is not None else []
    )
    return summary


@router.get(
    "/market/summary",
    tags=["Market"],
    summary="Get market sentiment summary",
    description="Returns a frontend-ready market sentiment score, ticker tape entries, and heatmap payload for the live market dashboard.",
)
async def get_market_summary(
    limit: int = Query(default=18, ge=6, le=50, description="Maximum number of symbols to scan."),
    request: Request = ...,
    container: ServiceContainer = Depends(get_container),
) -> dict:
    try:
        return await _market_summary_response(
            request=request,
            container=container,
            limit=limit,
        )
    except AuthenticationError as exc:
        raise HTTPException(status_code=403, detail=exc.to_dict()) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/market/summary",
    tags=["Market"],
    summary="Refresh market sentiment summary",
    description="POST variant of the market summary endpoint so the client can request a fresh sentiment snapshot for gauges and dashboard overlays.",
)
async def post_market_summary(
    payload: MarketSummaryRequest,
    request: Request,
    container: ServiceContainer = Depends(get_container),
) -> dict:
    try:
        return await _market_summary_response(
            request=request,
            container=container,
            limit=int(payload.limit),
        )
    except AuthenticationError as exc:
        raise HTTPException(status_code=403, detail=exc.to_dict()) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/test/mock-price-move",
    tags=["Diagnostics"],
    summary="Inject a mock market move for local trade-monitor validation",
    description="Shifts cached stream price, order book, and OHLCV candles for a symbol, then optionally runs the active trade monitor once so early-exit logic can be validated end-to-end.",
)
async def post_mock_price_move(
    payload: MockPriceMoveRequest,
    request: Request,
    container: ServiceContainer = Depends(get_container),
) -> dict:
    try:
        _ensure_debug_routes_enabled(container)
        authenticated_user_id = get_user_id(request)
        target_user_id = str(payload.user_id or authenticated_user_id).strip()
        _ensure_user_access(authenticated_user_id, target_user_id)
        symbol = str(payload.symbol or "").upper().strip()
        if not symbol:
            raise HTTPException(status_code=400, detail="symbol is required")

        analytics = getattr(container, "analytics_service", None)
        before_active = analytics.active_trades(target_user_id) if analytics is not None else []
        before_for_symbol = [trade for trade in before_active if str(trade.get("symbol", "") or "").upper() == symbol]
        move_result = container.market_data.inject_test_market_move(
            symbol,
            change=float(payload.change),
            volume_multiplier=float(payload.volume_multiplier),
        )

        monitor_ran = False
        if bool(payload.run_monitor) and getattr(container, "active_trade_monitor", None) is not None:
            await container.active_trade_monitor.run_once()
            monitor_ran = True

        after_active = analytics.active_trades(target_user_id) if analytics is not None else []
        after_for_symbol = [trade for trade in after_active if str(trade.get("symbol", "") or "").upper() == symbol]
        before_ids = {str(trade.get("trade_id", "") or "") for trade in before_for_symbol}
        after_ids = {str(trade.get("trade_id", "") or "") for trade in after_for_symbol}
        closed_ids = sorted(trade_id for trade_id in before_ids - after_ids if trade_id)
        history = analytics.trade_history(target_user_id, limit=25) if analytics is not None else []
        closed_records = [trade for trade in history if str(trade.get("trade_id", "") or "") in closed_ids]
        return {
            "symbol": symbol,
            "user_id": target_user_id,
            "move": move_result,
            "monitor_ran": monitor_ran,
            "before_active_count": len(before_for_symbol),
            "after_active_count": len(after_for_symbol),
            "closed_trade_ids": closed_ids,
            "closed_trades": closed_records,
            "remaining_active_trades": after_for_symbol,
        }
    except AuthenticationError as exc:
        raise HTTPException(status_code=403, detail=exc.to_dict()) from exc
    except HTTPException:
        raise
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
                **_signal_quality_fields_from_payload(payload),
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
    forced_execution_override = signal.strategy == "FORCED_PAPER_TRADE"
    low_confidence = bool(
        not forced_execution_override
        and (
            signal.strategy == "LOW_CONFIDENCE_WATCHLIST"
            or confidence < max(container.settings.signal_min_publish_confidence, 0.4)
            or not signal.alpha_decision.allow_trade
        )
    )
    action = signal.inference.decision
    if action == "HOLD":
        action = "BUY" if float(signal.snapshot.features.get("15m_ema_spread", 0.0)) >= 0 else "SELL"
    rejection_reason = None
    if forced_execution_override:
        rejection_reason = "force_execution_override"
    elif signal.inference.model_version == "best_effort_watchlist":
        rejection_reason = "best_effort_generation"
    elif not signal.alpha_decision.allow_trade:
        rejection_reason = "alpha_engine_rejected"
    elif low_confidence:
        rejection_reason = "low_confidence_watchlist"
    alpha_score = float(signal.alpha_decision.final_score)
    required_tier = "free" if low_confidence else "vip" if alpha_score >= 90 else "pro" if alpha_score >= 80 else "free"
    min_balance = 0.0 if low_confidence else max(container.settings.exchange_min_notional, 25.0 if alpha_score >= 80 else container.settings.exchange_min_notional)
    published_at = signal.snapshot.timestamp
    quality_reasons: list[str] = []
    if rejection_reason:
        quality_reasons.append(rejection_reason)
    strict_reason = str(signal.snapshot.features.get("strict_trade_reason", "") or "").strip()
    if strict_reason:
        quality_reasons.append(strict_reason)
    quality_reasons = list(dict.fromkeys(reason for reason in quality_reasons if reason))
    strict_trade_score = float(signal.snapshot.features.get("strict_trade_score", alpha_score) or 0.0)
    execution_allowed = bool(signal.alpha_decision.allow_trade and not low_confidence and signal.strategy not in {"NO_TRADE", "LOW_CONFIDENCE_WATCHLIST"})
    quality = "approved" if execution_allowed else "degraded" if rejection_reason == "best_effort_generation" else "watchlist" if low_confidence else "blocked"
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
        quality=quality,
        quality_score=round(max(0.0, min(strict_trade_score, 100.0)), 2),
        quality_reasons=quality_reasons,
        execution_allowed=execution_allowed,
        market_data_stale=False,
        market_data_sources={},
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
                quality="degraded",
                quality_score=0.0,
                quality_reasons=["live_generation_unavailable"],
                execution_allowed=False,
                market_data_stale=True,
                market_data_sources={},
            )
        )
        if len(items) >= max(1, limit):
            break
    return items


def _signal_quality_fields_from_payload(payload: dict) -> dict:
    pipeline_diagnostics = payload.get("pipeline_diagnostics") or {}
    market_data = pipeline_diagnostics.get("market_data") or {}
    rejection_reason = str(payload.get("rejection_reason") or "").strip()
    rejection_reasons = list(pipeline_diagnostics.get("rejection_reasons") or [])
    if rejection_reason:
        rejection_reasons.append(rejection_reason)
    strict_reason = str((payload.get("feature_snapshot") or {}).get("strict_trade_reason", "") or "").strip()
    if strict_reason:
        rejection_reasons.append(strict_reason)
    quality_reasons = list(dict.fromkeys(str(reason) for reason in rejection_reasons if str(reason or "").strip()))
    low_confidence = bool(payload.get("low_confidence", False))
    degraded_mode = bool(payload.get("degraded_mode", False))
    strategy = str(payload.get("strategy", "") or "").upper()
    final_trade_status = str(payload.get("final_trade_status", "") or "").lower()
    execution_allowed = bool(
        not low_confidence
        and not degraded_mode
        and strategy not in {"NO_TRADE", "LOW_CONFIDENCE_WATCHLIST"}
        and (
            final_trade_status == "accepted"
            or (not quality_reasons and final_trade_status in {"", "approved"})
        )
    )
    if degraded_mode or rejection_reason == "live_generation_unavailable":
        quality = "degraded"
    elif execution_allowed:
        quality = "approved"
    elif low_confidence:
        quality = "watchlist"
    else:
        quality = "blocked"
    quality_score = float(
        (payload.get("feature_snapshot") or {}).get(
            "strict_trade_score",
            payload.get("alpha_score", float(payload.get("confidence", 0.0) or 0.0) * 100),
        )
        or 0.0
    )
    market_data_sources = {
        str(key): str(value)
        for key, value in (market_data.get("sources") or {}).items()
        if value is not None
    }
    return {
        "quality": quality,
        "quality_score": round(max(0.0, min(quality_score, 100.0)), 2),
        "quality_reasons": quality_reasons,
        "execution_allowed": execution_allowed,
        "market_data_stale": bool(market_data.get("stale", False)) or bool(market_data.get("empty_intervals")),
        "market_data_sources": market_data_sources,
    }


def _live_signals_response_cache_key(viewer_subscription: dict, limit: int) -> str:
    user_id = str(viewer_subscription.get("user_id", "anonymous")).strip() or "anonymous"
    return f"signals:live:route:v1:{user_id}:{int(limit)}"


def _cache_get_json_safe(container: ServiceContainer, key: str) -> dict | None:
    try:
        get_json = getattr(container.cache, "get_json", None)
        if get_json is None:
            return None
        payload = get_json(key)
        return payload if isinstance(payload, dict) else None
    except Exception as exc:
        logger.warning(
            "route_cache_get_failed",
            extra={
                "event": "route_cache_get_failed",
                "context": {"key": key, "error": str(exc)[:200]},
            },
        )
        return None


def _cache_set_json_safe(container: ServiceContainer, key: str, value: dict, *, ttl: int) -> None:
    try:
        set_json = getattr(container.cache, "set_json", None)
        if set_json is None:
            return
        set_json(key, value, ttl=ttl)
    except Exception as exc:
        logger.warning(
            "route_cache_set_failed",
            extra={
                "event": "route_cache_set_failed",
                "context": {"key": key, "error": str(exc)[:200]},
            },
        )


def _log_route_timing(*, path: str, started: float, slow_threshold: float, context: dict | None = None) -> None:
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    logger.info(
        "endpoint_execution_timing",
        extra={
            "event": "endpoint_execution_timing",
            "context": {
                "path": path,
                "duration_ms": duration_ms,
                "slow": duration_ms >= slow_threshold * 1000,
                **(context or {}),
            },
        },
    )
    if duration_ms >= slow_threshold * 1000:
        logger.warning(
            "endpoint_execution_slow",
            extra={
                "event": "endpoint_execution_slow",
                "context": {"path": path, "duration_ms": duration_ms},
            },
        )


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
    "/risk/profile",
    tags=["User Portfolio"],
    summary="Get current risk profile",
    description="Returns the effective low, medium, or high risk profile for the authenticated user.",
)
async def get_risk_profile(
    user_id: str = Query(..., description="User identifier whose risk profile should be returned."),
    request: Request = ...,
    container: ServiceContainer = Depends(get_container),
) -> dict:
    try:
        authenticated_user_id = get_user_id(request)
        _ensure_user_access(authenticated_user_id, user_id)
        controller = getattr(container, "risk_controller", None)
        if controller is None:
            return {"level": "medium"}
        profile = controller.profile(user_id)
        return {
            "level": profile.level,
            "confidence_floor": profile.confidence_floor,
            "daily_loss_limit": profile.daily_loss_limit,
            "risk_fraction": profile.risk_fraction,
            "max_active_trades": profile.max_active_trades,
            "allowed_symbols": profile.allowed_symbols,
            "allow_counter_trend": profile.allow_counter_trend,
            "allow_high_volatility": profile.allow_high_volatility,
        }
    except AuthenticationError as exc:
        raise HTTPException(status_code=403, detail=exc.to_dict()) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/risk/profile",
    tags=["User Portfolio"],
    summary="Update risk profile",
    description="Sets the user's low, medium, or high risk profile and applies matching drawdown and rollout controls.",
)
async def update_risk_profile(
    user_id: str = Query(..., description="User identifier whose risk profile should be updated."),
    level: str = Query(..., pattern=r"^(low|medium|high)$", description="Risk level to apply."),
    request: Request = ...,
    container: ServiceContainer = Depends(get_container),
) -> dict:
    try:
        authenticated_user_id = get_user_id(request)
        _ensure_user_access(authenticated_user_id, user_id)
        controller = getattr(container, "risk_controller", None)
        if controller is None:
            return {"level": "medium"}
        profile = controller.set_profile(user_id, level)
        return {
            "level": profile.level,
            "confidence_floor": profile.confidence_floor,
            "daily_loss_limit": profile.daily_loss_limit,
            "risk_fraction": profile.risk_fraction,
            "max_active_trades": profile.max_active_trades,
            "allowed_symbols": profile.allowed_symbols,
            "allow_counter_trend": profile.allow_counter_trend,
            "allow_high_volatility": profile.allow_high_volatility,
        }
    except AuthenticationError as exc:
        raise HTTPException(status_code=403, detail=exc.to_dict()) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/engine/state",
    tags=["User Portfolio"],
    summary="Get trading engine state",
    description="Returns whether the authenticated user's trading engine is enabled or paused by a manual or automatic emergency stop.",
)
async def get_engine_state(
    user_id: str = Query(..., description="User identifier whose engine state should be returned."),
    request: Request = ...,
    container: ServiceContainer = Depends(get_container),
) -> dict:
    try:
        authenticated_user_id = get_user_id(request)
        _ensure_user_access(authenticated_user_id, user_id)
        controls = container.drawdown_protection.load_controls(user_id)
        return {
            "user_id": user_id,
            "enabled": not controls.emergency_stop_active,
            "manual_stop": bool(controls.emergency_stop_manual),
            "auto_stop": bool(controls.emergency_stop_auto),
            "reason": controls.emergency_stop_reason,
            "updated_at": controls.updated_at.isoformat() if controls.updated_at else None,
        }
    except AuthenticationError as exc:
        raise HTTPException(status_code=403, detail=exc.to_dict()) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/engine/state",
    tags=["User Portfolio"],
    summary="Update trading engine state",
    description="Enables or disables the authenticated user's trading engine using the manual emergency-stop control layer.",
)
async def update_engine_state(
    user_id: str = Query(..., description="User identifier whose engine state should be updated."),
    enabled: bool = Query(..., description="Whether trading should be enabled for the user."),
    request: Request = ...,
    container: ServiceContainer = Depends(get_container),
) -> dict:
    try:
        authenticated_user_id = get_user_id(request)
        _ensure_user_access(authenticated_user_id, user_id)
        if enabled:
            controls = container.drawdown_protection.clear_emergency_stop(user_id)
        else:
            controls = container.drawdown_protection.activate_emergency_stop(
                user_id,
                reason="manual_user_pause",
                manual=True,
            )
        return {
            "user_id": user_id,
            "enabled": not controls.emergency_stop_active,
            "manual_stop": bool(controls.emergency_stop_manual),
            "auto_stop": bool(controls.emergency_stop_auto),
            "reason": controls.emergency_stop_reason,
            "updated_at": controls.updated_at.isoformat() if controls.updated_at else None,
        }
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


def _normalize_marker_timestamp(value: object) -> str:
    if isinstance(value, datetime):
        normalized = value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return normalized.isoformat()
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
    text = str(value or "").strip()
    if not text:
        return datetime.fromtimestamp(0, tz=timezone.utc).isoformat()
    try:
        parsed = datetime.fromisoformat(text)
        normalized = parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        return normalized.isoformat()
    except ValueError:
        return text


def _build_market_markers(
    *,
    container: ServiceContainer,
    target_user_id: str,
    normalized_symbol: str,
    candles: list[dict[str, object]],
    latest_price: float,
) -> list[dict[str, object]]:
    analytics = getattr(container, "analytics_service", None)
    activity_engine = getattr(container, "user_experience_engine", None)
    active_trades = analytics.active_trades(target_user_id) if analytics is not None else []
    history_trades = analytics.trade_history(target_user_id, limit=120) if analytics is not None else []
    activity_items = activity_engine.history(limit=120) if activity_engine is not None else []
    markers: list[dict[str, object]] = []

    for trade in [*active_trades, *history_trades]:
        if str(trade.get("symbol", "")).upper() != normalized_symbol:
            continue
        trade_id = str(trade.get("trade_id", "") or "")
        entry = float(trade.get("entry", 0.0) or 0.0)
        exit_price = float(trade.get("exit", 0.0) or 0.0)
        side = str(trade.get("side", "") or "BUY")
        confidence_score = round(_coerce_confidence_score(trade), 8)
        opened_at = trade.get("opened_at") or trade.get("created_at") or trade.get("submitted_at")
        closed_at = trade.get("closed_at") or trade.get("updated_at")
        if entry > 0 and opened_at:
            marker_payload = _marker_logic_payload(
                source=trade,
                side=side,
                regime=str(trade.get("regime", "") or ""),
                confidence_score=confidence_score,
            )
            markers.append(
                {
                    "type": "entry",
                    "marker_type": "ENTRY",
                    "marker_style": "filled",
                    "trade_id": trade_id,
                    "side": side,
                    "price": round(entry, 8),
                    "timestamp": _normalize_marker_timestamp(opened_at),
                    "confidence_score": confidence_score,
                    "status": str(trade.get("status", "OPEN") or "OPEN"),
                    **marker_payload,
                }
            )
        if exit_price > 0 and closed_at:
            marker_payload = _marker_logic_payload(
                source=trade,
                side=side,
                regime=str(trade.get("regime", "") or ""),
                confidence_score=confidence_score,
            )
            markers.append(
                {
                    "type": "exit",
                    "marker_type": "EXIT",
                    "marker_style": "filled",
                    "trade_id": trade_id,
                    "side": side,
                    "price": round(exit_price, 8),
                    "timestamp": _normalize_marker_timestamp(closed_at),
                    "exit_reason": trade.get("exit_reason"),
                    "confidence_score": confidence_score,
                    "status": str(trade.get("status", "CLOSED") or "CLOSED"),
                    **marker_payload,
                }
            )

    for activity in activity_items:
        if str(activity.get("symbol", "")).upper() != normalized_symbol:
            continue
        status = str(activity.get("status", "") or "").lower().strip()
        if status not in {"almost_trade", "scanning", "waiting"}:
            continue
        confidence_score = _coerce_confidence_score(activity)
        readiness_score = float(activity.get("readiness", 0.0) or 0.0)
        if confidence_score <= 0 and readiness_score <= 0:
            continue
        timestamp = activity.get("timestamp") or activity.get("updated_at")
        if not timestamp:
            continue
        markers.append(
            {
                "type": "ghost",
                "marker_type": "REJECTED_SETUP",
                "marker_style": "ghost",
                "side": str(activity.get("action", "") or "WATCH"),
                "price": round(_resolve_marker_price(activity, candles, latest_price), 8),
                "timestamp": _normalize_marker_timestamp(timestamp),
                "confidence_score": round(confidence_score, 8),
                "readiness_score": round(readiness_score, 2),
                "status": str(activity.get("status", "") or "").upper(),
                "reason": activity.get("reason"),
                "message": activity.get("message"),
                "intent": activity.get("intent"),
                **_marker_logic_payload(
                    source=activity,
                    side=str(activity.get("action", "") or "WATCH"),
                    regime=str(activity.get("regime", "") or ""),
                    confidence_score=confidence_score,
                ),
            }
        )

    return _dedupe_market_markers(markers)


def _dedupe_market_markers(markers: list[dict[str, object]]) -> list[dict[str, object]]:
    deduped: list[dict[str, object]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for marker in sorted(markers, key=lambda item: str(item.get("timestamp", ""))):
        key = (
            str(marker.get("marker_type", "") or ""),
            str(marker.get("trade_id", "") or ""),
            str(marker.get("timestamp", "") or ""),
            f"{float(marker.get('price', 0.0) or 0.0):.8f}",
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(marker)
    return deduped


def _build_confidence_intervals(
    *,
    candles: list[dict[str, object]],
    markers: list[dict[str, object]],
) -> list[dict[str, object]]:
    if not candles:
        return []
    candle_scores = [0.0 for _ in candles]
    for marker in markers:
        confidence = _coerce_confidence_score(marker)
        if confidence < 0.6:
            continue
        marker_index = _nearest_candle_index(
            candles=candles,
            timestamp_ms=_timestamp_to_epoch_ms(marker.get("timestamp")),
        )
        if marker_index is None:
            continue
        if str(marker.get("marker_style", "") or "") == "ghost":
            radius = 2 if confidence >= 0.8 else 1
            for index in range(
                max(0, marker_index - radius),
                min(len(candles), marker_index + radius + 1),
            ):
                candle_scores[index] = max(candle_scores[index], confidence)

    trade_windows: dict[str, dict[str, int | float]] = {}
    for marker in markers:
        trade_id = str(marker.get("trade_id", "") or "").strip()
        confidence = _coerce_confidence_score(marker)
        if not trade_id or confidence < 0.6:
            continue
        marker_index = _nearest_candle_index(
            candles=candles,
            timestamp_ms=_timestamp_to_epoch_ms(marker.get("timestamp")),
        )
        if marker_index is None:
            continue
        window = trade_windows.setdefault(
            trade_id,
            {"start": marker_index, "end": marker_index, "confidence": confidence},
        )
        marker_type = str(marker.get("marker_type", "") or "")
        if marker_type == "ENTRY":
            window["start"] = marker_index
        elif marker_type == "EXIT":
            window["end"] = marker_index
        else:
            window["start"] = min(int(window["start"]), marker_index)
            window["end"] = max(int(window["end"]), marker_index)
        window["confidence"] = max(float(window["confidence"]), confidence)

    for window in trade_windows.values():
        start = max(0, min(int(window["start"]), int(window["end"])))
        end = min(len(candles) - 1, max(int(window["start"]), int(window["end"])))
        confidence = float(window["confidence"])
        for index in range(start, end + 1):
            candle_scores[index] = max(candle_scores[index], confidence)

    intervals: list[dict[str, object]] = []
    start_index: int | None = None
    active_scores: list[float] = []
    for index, score in enumerate(candle_scores):
        if score >= 0.6:
            if start_index is None:
                start_index = index
                active_scores = []
            active_scores.append(score)
            continue
        if start_index is not None:
            intervals.append(
                _confidence_interval_payload(
                    candles=candles,
                    start_index=start_index,
                    end_index=index - 1,
                    scores=active_scores,
                )
            )
            start_index = None
            active_scores = []
    if start_index is not None:
        intervals.append(
            _confidence_interval_payload(
                candles=candles,
                start_index=start_index,
                end_index=len(candles) - 1,
                scores=active_scores,
            )
        )
    return intervals


def _marker_logic_payload(
    *,
    source: dict,
    side: str,
    regime: str,
    confidence_score: float,
) -> dict[str, object]:
    existing_breakdown = source.get("confluence_breakdown")
    confluence_breakdown = (
        {
            str(key): str(value)
            for key, value in dict(existing_breakdown or {}).items()
            if str(key).strip() and str(value).strip()
        }
        if isinstance(existing_breakdown, dict)
        else {}
    )
    if not confluence_breakdown:
        confluence_breakdown = _infer_confluence_breakdown(
            entry_reason=str(source.get("entry_reason", source.get("reason", "")) or ""),
            regime=regime,
            side=side,
        )

    existing_risk = source.get("risk_flags")
    risk_flags = (
        {
            str(key): value
            for key, value in dict(existing_risk or {}).items()
            if str(key).strip()
        }
        if isinstance(existing_risk, dict)
        else {}
    )
    if not risk_flags:
        risk_flags = _infer_risk_flags(
            regime=regime,
            confidence_score=confidence_score,
            source=source,
        )

    logic_tags = [
        str(tag)
        for tag in (source.get("logic_tags") or source.get("tags") or [])
        if str(tag).strip()
    ]
    if not logic_tags:
        logic_tags = _infer_logic_tags(
            entry_reason=str(source.get("entry_reason", source.get("reason", "")) or ""),
            regime=regime,
            side=side,
        )

    aligned = sum(
        1
        for value in confluence_breakdown.values()
        if any(
            token in str(value).lower()
            for token in ("aligned", "spiking", "supportive", "breakout", "acceptable", "oversold", "bullish", "tight")
        )
    )
    total = max(len(confluence_breakdown), 1)
    return {
        "confluence_breakdown": confluence_breakdown,
        "confluence_aligned": int(aligned),
        "confluence_total": int(total),
        "risk_flags": risk_flags,
        "logic_tags": logic_tags[:3],
    }


def _infer_confluence_breakdown(
    *,
    entry_reason: str,
    regime: str,
    side: str,
) -> dict[str, str]:
    reason = entry_reason.lower()
    normalized_side = str(side or "").upper()
    return {
        "structure": "Bullish breakout aligned"
        if ("structure" in reason or "breakout" in reason or "trend" in reason) and normalized_side != "SELL"
        else "Bearish breakdown aligned"
        if ("structure" in reason or "breakdown" in reason) and normalized_side == "SELL"
        else "Structure scan active",
        "volume": "Volume spiking" if "volume" in reason else "Volume watch",
        "momentum": "Momentum supportive" if any(token in reason for token in ("momentum", "mfi", "rsi")) else "Momentum mixed",
        "trend": "Bullish trend regime"
        if str(regime).upper() == "TRENDING" and normalized_side != "SELL"
        else "Bearish trend regime"
        if str(regime).upper() == "TRENDING" and normalized_side == "SELL"
        else "Trend still forming",
    }


def _infer_risk_flags(
    *,
    regime: str,
    confidence_score: float,
    source: dict,
) -> dict[str, str | bool]:
    exit_reason = str(source.get("exit_reason", "") or "").lower()
    return {
        "volatility": "High" if str(regime).upper() == "HIGH_VOL" or "reversal" in exit_reason else "Contained",
        "spread": "Tight" if confidence_score >= 0.7 else "Watch",
        "liquidity_warning": bool(confidence_score < 0.45),
    }


def _infer_logic_tags(
    *,
    entry_reason: str,
    regime: str,
    side: str,
) -> list[str]:
    reason = entry_reason.lower()
    tags: list[str] = []
    if "breakout" in reason or "volume" in reason:
        tags.append("#BreakoutHunter")
    if "rsi" in reason or "reversion" in reason:
        tags.append("#MeanReversion")
    if str(regime).upper() == "TRENDING":
        tags.append("#TrendFollowing")
    if not tags and str(side).upper() in {"BUY", "SELL"}:
        tags.append("#MomentumProbe")
    return tags


def _confidence_interval_payload(
    *,
    candles: list[dict[str, object]],
    start_index: int,
    end_index: int,
    scores: list[float],
) -> dict[str, object]:
    score = max(scores) if scores else 0.0
    return {
        "start_ts": int(candles[start_index].get("timestamp", 0) or 0),
        "end_ts": int(candles[end_index].get("timestamp", 0) or 0),
        "score": round(score, 4),
        "zone_type": "STRONG_CONVICTION" if score >= 0.8 else "SOFT_CONVICTION",
    }


def _nearest_candle_index(
    *,
    candles: list[dict[str, object]],
    timestamp_ms: int,
) -> int | None:
    if not candles or timestamp_ms <= 0:
        return None
    best_index = None
    best_diff = None
    for index, candle in enumerate(candles):
        diff = abs(int(candle.get("timestamp", 0) or 0) - timestamp_ms)
        if best_diff is None or diff < best_diff:
            best_index = index
            best_diff = diff
    return best_index


def _coerce_confidence_score(payload: dict) -> float:
    return max(
        0.0,
        min(
            float(
                payload.get(
                    "confidence_score",
                    payload.get(
                        "confidence_meter",
                        payload.get("confidence", payload.get("trade_success_probability", 0.0)),
                    ),
                )
                or 0.0
            ),
            1.0,
        ),
    )


def _resolve_marker_price(
    activity: dict,
    candles: list[dict[str, object]],
    latest_price: float,
) -> float:
    explicit_price = float(
        activity.get("price", activity.get("reference_price", activity.get("trigger_price", 0.0))) or 0.0
    )
    if explicit_price > 0:
        return explicit_price
    target_ms = _timestamp_to_epoch_ms(activity.get("timestamp") or activity.get("updated_at"))
    if target_ms > 0 and candles:
        closest = min(
            candles,
            key=lambda candle: abs(int(candle.get("timestamp", 0) or 0) - target_ms),
        )
        return float(closest.get("close", latest_price) or latest_price)
    return float(latest_price or 0.0)


def _timestamp_to_epoch_ms(value: object) -> int:
    text = _normalize_marker_timestamp(value)
    try:
        parsed = datetime.fromisoformat(text)
        normalized = parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        return int(normalized.timestamp() * 1000)
    except ValueError:
        return 0


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

