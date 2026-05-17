from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

from app.schemas.trading import SignalResponse
from app.services.advanced_risk_intelligence import AdvancedRiskIntelligence
from app.services.autonomous_assistant_engine import AutonomousAssistantEngine
from app.services.market_regime_engine import MarketRegimeEngine
from app.services.multi_agent_intelligence import MultiAgentIntelligenceEngine
from app.services.orderbook_depth_engine import FullDepthOrderbookEngine
from app.services.orderflow_engine import InstitutionalOrderflowEngine
from app.services.predictive_intelligence import PredictiveIntelligenceEngine
from app.services.render_profile_engine import RenderProfileEngine
from app.trading.exits import initial_exit_plan

ASSISTANT_MODES = ("MANUAL", "ASSISTED", "SEMI_AUTO", "FULL_AUTO")
SCALP_INTERVALS = ("1m", "3m", "5m", "15m")


def resample_ohlcv(frame: pd.DataFrame | None, *, minutes: int) -> pd.DataFrame:
    if frame is None or getattr(frame, "empty", True):
        return pd.DataFrame()
    working = frame.copy()
    for column in ("open", "high", "low", "close", "volume"):
        working[column] = working[column].astype(float)
    time_column = "open_time" if "open_time" in working.columns else "close_time"
    working["_timestamp"] = pd.to_datetime(working[time_column], unit="ms", utc=True)
    aggregated = (
        working.set_index("_timestamp")
        .resample(f"{int(minutes)}min", label="right", closed="right")
        .agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )
        .dropna()
        .reset_index()
    )
    if aggregated.empty:
        return pd.DataFrame()
    aggregated["open_time"] = (
        aggregated["_timestamp"] - pd.to_timedelta(minutes, unit="min")
    ).astype("int64") // 10**6
    aggregated["close_time"] = aggregated["_timestamp"].astype("int64") // 10**6
    return aggregated[
        ["open_time", "close_time", "open", "high", "low", "close", "volume"]
    ].copy()


def build_chart_intelligence(
    *,
    symbol: str,
    interval: str,
    frame: pd.DataFrame | None,
    signal: SignalResponse | None = None,
    existing_markers: list[dict[str, Any]] | None = None,
    analytics_summary: dict[str, Any] | None = None,
    assistant_mode: str = "ASSISTED",
    learning_enabled: bool = False,
) -> dict[str, Any]:
    prepared = _prepare_frame(frame)
    if prepared.empty:
        return _empty_payload(
            symbol=symbol,
            interval=interval,
            assistant_mode=assistant_mode,
        )

    latest = prepared.iloc[-1]
    recent = prepared.tail(min(len(prepared), 72)).copy()
    closes = recent["close"].astype(float)
    highs = recent["high"].astype(float)
    lows = recent["low"].astype(float)
    volumes = recent["volume"].astype(float)
    avg_volume = float(volumes.tail(min(len(volumes), 20)).mean() or 0.0)
    last_volume = float(volumes.iloc[-1] or 0.0)
    volume_ratio = last_volume / max(avg_volume, 1e-8)
    volatility = float(
        signal.snapshot.volatility
        if signal is not None
        else closes.pct_change().dropna().tail(24).std(ddof=0) or 0.0
    )
    atr = float(signal.snapshot.atr if signal is not None else _atr(recent.tail(20)))
    spread_bps = float(
        signal.snapshot.features.get("spread_bps", 0.0)
        if signal is not None
        else 0.0
    )
    ema_fast = closes.ewm(span=5, adjust=False).mean()
    ema_slow = closes.ewm(span=13, adjust=False).mean()
    ema_anchor = closes.ewm(span=21, adjust=False).mean()
    trend_strength = _clamp(
        abs(float(ema_fast.iloc[-1] - ema_slow.iloc[-1]))
        / max(float(latest["close"]), 1e-8)
        / 0.01,
        0.0,
        1.0,
    )
    momentum_score = _clamp(
        abs(float(closes.iloc[-1] - closes.iloc[max(0, len(closes) - 6)]))
        / max(float(latest["close"]) * max(volatility, 0.003), 1e-8),
        0.0,
        1.0,
    )
    volatility_score = _clamp(volatility / 0.025, 0.0, 1.0)
    whale_pressure = _whale_pressure(signal)
    confidence = _confidence_score(signal, momentum_score, trend_strength)
    decision_side = _decision_side(signal, ema_fast.iloc[-1], ema_slow.iloc[-1])
    regime = _market_regime(
        closes=closes,
        highs=highs,
        lows=lows,
        volumes=volumes,
        volatility=volatility,
        volume_ratio=volume_ratio,
        spread_bps=spread_bps,
        ema_fast=float(ema_fast.iloc[-1]),
        ema_slow=float(ema_slow.iloc[-1]),
    )
    advanced_regime = MarketRegimeEngine().analyze(recent)
    orderflow = InstitutionalOrderflowEngine().analyze(
        recent,
        spread_bps=spread_bps,
    )
    orderbook = FullDepthOrderbookEngine.synthetic_from_price(
        price=float(latest["close"]),
        atr=max(atr, float(latest["close"]) * 0.0015),
        sequence_id=int(latest.get("close_time", latest.get("open_time", 1)) or 1),
    ).analyze()
    exit_plan = initial_exit_plan(
        side=decision_side,
        entry_price=float(latest["close"]),
        atr=max(atr, float(latest["close"]) * 0.0015),
        volatility=max(volatility, 0.003),
        take_profit_rr=max(1.35, 1.2 + momentum_score),
    )
    support = float(lows.tail(min(len(lows), 20)).quantile(0.2))
    resistance = float(highs.tail(min(len(highs), 20)).quantile(0.8))
    range_mid = (support + resistance) / 2
    current_price = float(latest["close"])
    expected_rr = _expected_rr(
        entry=current_price,
        stop_loss=exit_plan.stop_loss,
        take_profit=exit_plan.take_profit,
    )
    scalp_score = _clamp(
        (confidence * 0.30)
        + (momentum_score * 0.22)
        + (trend_strength * 0.18)
        + (volatility_score * 0.12)
        + (whale_pressure * 0.18),
        0.0,
        1.0,
    )

    sweep_up = bool(
        len(recent) >= 8
        and float(latest["high"]) > float(highs.iloc[-8:-1].max())
        and float(latest["close"]) < float(highs.iloc[-8:-1].max())
    )
    sweep_down = bool(
        len(recent) >= 8
        and float(latest["low"]) < float(lows.iloc[-8:-1].min())
        and float(latest["close"]) > float(lows.iloc[-8:-1].min())
    )
    trend_shift = bool(
        len(ema_fast) >= 2
        and ((float(ema_fast.iloc[-1]) >= float(ema_slow.iloc[-1]) and float(ema_fast.iloc[-2]) < float(ema_slow.iloc[-2]))
        or (float(ema_fast.iloc[-1]) <= float(ema_slow.iloc[-1]) and float(ema_fast.iloc[-2]) > float(ema_slow.iloc[-2])))
    )
    smc = _smc_payload(
        recent=recent,
        side=decision_side,
        current_price=current_price,
        atr=max(atr, current_price * 0.0015),
        confidence=confidence,
        trend_strength=trend_strength,
        momentum_score=momentum_score,
        volume_ratio=volume_ratio,
        sweep_up=sweep_up,
        sweep_down=sweep_down,
        trend_shift=trend_shift,
    )
    confidence_engine = _ai_confidence_engine(
        signal=signal,
        regime=regime["state"],
        confidence=confidence,
        trend_strength=trend_strength,
        momentum_score=momentum_score,
        volatility_score=volatility_score,
        volume_ratio=volume_ratio,
        spread_bps=spread_bps,
        smc_confluence=float(smc["confluence_score"]) / 100.0,
        breakout_strength=float(smc["breakout_strength"]),
    )
    multi_agent_intelligence = MultiAgentIntelligenceEngine().evaluate(
        side=decision_side,
        confidence=confidence,
        smc_confluence=float(smc["confluence_score"]) / 100.0,
        liquidity_pressure=orderflow.liquidity_pressure_score,
        regime_confidence=advanced_regime.confidence,
        trap_probability=orderflow.trap_probability,
        momentum_score=momentum_score,
        risk_score=float(confidence_engine["risk_score"]) / 100.0,
    )
    predictive_intelligence = PredictiveIntelligenceEngine().predict(
        current_price=current_price,
        atr=max(atr, current_price * 0.0015),
        confidence=confidence,
        trend_strength=trend_strength,
        momentum_score=momentum_score,
        trap_probability=orderflow.trap_probability,
        regime=advanced_regime.regime,
        side=decision_side,
    )
    advanced_risk = AdvancedRiskIntelligence().evaluate(
        volatility=volatility,
        spread_bps=spread_bps,
        trap_probability=orderflow.trap_probability,
        liquidity_pressure=orderflow.liquidity_pressure_score,
        confidence=confidence,
        regime=advanced_regime.regime,
    )
    autonomous_assistant = AutonomousAssistantEngine().summarize(
        symbol=symbol,
        orderbook=orderbook.as_dict(),
        orderflow=orderflow.as_dict(),
        predictive=predictive_intelligence,
        risk=advanced_risk,
        regime={"state": advanced_regime.regime, "confidence": advanced_regime.confidence},
    )

    tp_distance = abs(exit_plan.take_profit - current_price)
    stop_distance = abs(current_price - exit_plan.stop_loss)
    tp1 = current_price + (tp_distance * 0.55) if decision_side == "BUY" else current_price - (tp_distance * 0.55)
    tp2 = exit_plan.take_profit
    entry_low = current_price - (stop_distance * 0.18) if decision_side == "BUY" else current_price - (tp_distance * 0.12)
    entry_high = current_price + (tp_distance * 0.12) if decision_side == "BUY" else current_price + (stop_distance * 0.18)
    trailing = _trailing_payload(
        side=decision_side,
        current_price=current_price,
        stop_loss=exit_plan.stop_loss,
        atr=max(atr, current_price * 0.0015),
        ema_anchor=float(ema_anchor.iloc[-1]),
        volatility=max(volatility, 0.003),
        interval=interval,
    )

    synthetic_markers = _synthetic_markers(
        symbol=symbol,
        interval=interval,
        recent=recent,
        side=decision_side,
        confidence=confidence,
        support=support,
        resistance=resistance,
        sweep_up=sweep_up,
        sweep_down=sweep_down,
        trend_shift=trend_shift,
    )
    synthetic_markers.extend(smc["markers"])
    overlay_zones = [
        _zone_payload(
            zone_type="breakout_zone",
            label="Breakout Compression",
            start_ts=_ts_ms(recent.iloc[max(0, len(recent) - 10)]),
            end_ts=_ts_ms(latest),
            low=min(support, range_mid),
            high=max(resistance, range_mid),
            confidence=confidence,
            side=decision_side,
            style="neutral",
        ),
        _zone_payload(
            zone_type="reversal_zone",
            label="Reversal Pocket",
            start_ts=_ts_ms(recent.iloc[max(0, len(recent) - 6)]),
            end_ts=_ts_ms(latest),
            low=current_price - (atr * 0.9),
            high=current_price + (atr * 0.9),
            confidence=max(0.45, confidence * 0.78),
            side=decision_side,
            style="warning",
        ),
        _zone_payload(
            zone_type="support_resistance",
            label="Support",
            start_ts=_ts_ms(recent.iloc[0]),
            end_ts=_ts_ms(latest),
            low=support * 0.999,
            high=support * 1.001,
            confidence=max(0.45, trend_strength),
            side="BUY",
            style="bullish",
        ),
        _zone_payload(
            zone_type="support_resistance",
            label="Resistance",
            start_ts=_ts_ms(recent.iloc[0]),
            end_ts=_ts_ms(latest),
            low=resistance * 0.999,
            high=resistance * 1.001,
            confidence=max(0.45, trend_strength),
            side="SELL",
            style="bearish",
        ),
        _zone_payload(
            zone_type="stop_loss_zone",
            label="Stop Loss",
            start_ts=_ts_ms(recent.iloc[max(0, len(recent) - 6)]),
            end_ts=_ts_ms(latest),
            low=min(exit_plan.stop_loss, exit_plan.stop_loss * 1.0015),
            high=max(exit_plan.stop_loss, exit_plan.stop_loss * 1.0015),
            confidence=0.95,
            side=decision_side,
            style="risk",
        ),
        _zone_payload(
            zone_type="take_profit_zone",
            label="TP1",
            start_ts=_ts_ms(recent.iloc[max(0, len(recent) - 6)]),
            end_ts=_ts_ms(latest),
            low=min(tp1, tp1 * 1.0012),
            high=max(tp1, tp1 * 1.0012),
            confidence=max(0.60, confidence),
            side=decision_side,
            style="reward",
        ),
        _zone_payload(
            zone_type="take_profit_zone",
            label="TP2",
            start_ts=_ts_ms(recent.iloc[max(0, len(recent) - 6)]),
            end_ts=_ts_ms(latest),
            low=min(tp2, tp2 * 1.0012),
            high=max(tp2, tp2 * 1.0012),
            confidence=max(0.66, confidence),
            side=decision_side,
            style="reward",
        ),
        _zone_payload(
            zone_type="trailing_stop",
            label=f"{trailing['mode']} Trail",
            start_ts=_ts_ms(recent.iloc[max(0, len(recent) - 6)]),
            end_ts=_ts_ms(latest),
            low=min(trailing["current_stop"], trailing["projected_stop"]),
            high=max(trailing["current_stop"], trailing["projected_stop"]),
            confidence=max(0.50, confidence * 0.82),
            side=decision_side,
            style="trail",
        ),
    ]
    if sweep_up or sweep_down:
        overlay_zones.append(
            _zone_payload(
                zone_type="liquidity_sweep",
                label="Liquidity Sweep",
                start_ts=_ts_ms(recent.iloc[max(0, len(recent) - 3)]),
                end_ts=_ts_ms(latest),
                low=float(latest["low"]),
                high=float(latest["high"]),
                confidence=max(0.6, confidence),
                side="SELL" if sweep_up else "BUY",
                style="warning",
            )
        )
    if trend_shift:
        overlay_zones.append(
            _zone_payload(
                zone_type="trend_shift",
                label="Trend Shift",
                start_ts=_ts_ms(recent.iloc[max(0, len(recent) - 5)]),
                end_ts=_ts_ms(latest),
                low=float(latest["low"]),
                high=float(latest["high"]),
                confidence=max(0.58, trend_strength),
                side=decision_side,
                style="accent",
            )
        )
    overlay_zones.extend(smc["overlays"])
    liquidity_heatmap = _liquidity_heatmap(
        recent=recent,
        support=support,
        resistance=resistance,
        current_price=current_price,
        volume_ratio=volume_ratio,
        confidence=confidence,
        orderflow_pressure=orderflow.liquidity_pressure_score,
    )
    overlay_zones.extend(liquidity_heatmap["overlays"])
    render_profile = RenderProfileEngine().profile(
        overlay_count=len(overlay_zones),
        heatmap_zones=len(liquidity_heatmap["summary"].get("heatmap_zones", [])),
        dom_levels=len(orderbook.liquidity_ladder),
        fps=60.0,
    )

    analytics_summary = analytics_summary or {}
    micro_strategies = _micro_strategies(
        scalp_score=scalp_score,
        confidence=confidence,
        momentum_score=momentum_score,
        volume_ratio=volume_ratio,
        sweep_up=sweep_up,
        sweep_down=sweep_down,
        trend_shift=trend_shift,
        regime=regime["state"],
    )
    ai_feed = _ai_feed(
        symbol=symbol,
        regime=regime["state"],
        confidence=confidence,
        scalp_score=scalp_score,
        sweep_up=sweep_up,
        sweep_down=sweep_down,
        trend_shift=trend_shift,
        momentum_score=momentum_score,
        volume_ratio=volume_ratio,
    )
    latest_ts = _ts_ms(latest)
    if signal is not None and signal.inference.decision in {"BUY", "SELL"}:
        synthetic_markers.insert(
            0,
            {
                "type": "signal",
                "marker_type": signal.inference.decision,
                "marker_style": "outline",
                "side": signal.inference.decision,
                "price": round(current_price, 8),
                "timestamp": _ts_iso(latest_ts),
                "confidence_score": round(confidence, 8),
                "reason": signal.inference.reason,
                "message": signal.alpha.explainability.human_reason or signal.inference.reason,
                "intent": f"{signal.strategy} scalp setup",
                "logic_tags": ["ai_signal", regime["state"].lower(), interval],
                "risk_flags": {"low_liquidity": regime["state"] == "LOW_LIQUIDITY"},
            },
        )

    return {
        "chart_engine": "custom_canvas_pro",
        "scalp_engine": {
            "optimized_intervals": list(SCALP_INTERVALS),
            "active_interval": interval,
            "scalp_score": round(scalp_score * 100, 2),
            "dominant_setup": max(
                micro_strategies,
                key=lambda item: float(item.get("score", 0.0) or 0.0),
            )["name"]
            if micro_strategies
            else "Adaptive Micro Flow",
        },
        "opportunity": {
            "confidence": round(confidence * 100, 2),
            "expected_rr": round(expected_rr, 3),
            "momentum_score": round(momentum_score * 100, 2),
            "volatility_score": round(volatility_score * 100, 2),
            "whale_pressure": round(whale_pressure * 100, 2),
            "trend_strength": round(trend_strength * 100, 2),
            "scalp_score": round(scalp_score * 100, 2),
        },
        "market_regime": regime,
        "advanced_market_regime": {
            "state": advanced_regime.regime,
            "confidence": round(advanced_regime.confidence * 100, 2),
            "transition_probability": round(advanced_regime.transition_probability * 100, 2),
            "strategy_suitability": advanced_regime.strategy_suitability,
            "ai_modifiers": advanced_regime.ai_modifiers,
            "reasons": advanced_regime.reasons,
        },
        "assistant_modes": list(ASSISTANT_MODES),
        "active_assistant_mode": _normalize_mode(assistant_mode),
        "execution_guide": {
            "side": decision_side,
            "entry_zone": {
                "low": round(min(entry_low, entry_high), 8),
                "high": round(max(entry_low, entry_high), 8),
            },
            "stop_loss": round(exit_plan.stop_loss, 8),
            "tp1": round(tp1, 8),
            "tp2": round(tp2, 8),
            "trailing_stop_path": trailing["path"],
            "risk_reward": round(expected_rr, 3),
            "risk_visualization": {
                "risk_pct": round(stop_distance / max(current_price, 1e-8) * 100, 3),
                "reward_pct": round(tp_distance / max(current_price, 1e-8) * 100, 3),
            },
        },
        "strategy_state": {
            "active_strategy": signal.strategy if signal is not None else "ADAPTIVE_SCALP_ENGINE",
            "active_timeframe": interval,
            "learns_from_successful_trades": bool(learning_enabled),
            "current_win_rate": round(float(analytics_summary.get("win_rate", 0.0) or 0.0) * 100, 2),
            "promoted_strategies": [
                strategy["name"]
                for strategy in micro_strategies
                if float(strategy.get("score", 0.0) or 0.0) >= 78.0
            ],
            "micro_strategies": micro_strategies,
            "best_regime": str(analytics_summary.get("best_regime", regime["state"]) or regime["state"]),
        },
        "ai_feed": ai_feed,
        "smc": {
            "structures": smc["structures"],
            "confluence_score": smc["confluence_score"],
            "breakout_strength": round(float(smc["breakout_strength"]) * 100, 2),
            "premium_discount": smc["premium_discount"],
            "summary": smc["summary"],
        },
        "ai_confidence_engine": confidence_engine,
        "orderflow": orderflow.as_dict(),
        "orderbook_depth": orderbook.as_dict(),
        "multi_agent_intelligence": multi_agent_intelligence,
        "predictive_intelligence": predictive_intelligence,
        "advanced_risk_intelligence": advanced_risk,
        "autonomous_assistant": autonomous_assistant,
        "multi_timeframe_intelligence": _multi_timeframe_intelligence(
            interval=interval,
            side=decision_side,
            trend_strength=trend_strength,
            momentum_score=momentum_score,
            smc_confluence=float(smc["confluence_score"]) / 100.0,
            confidence=confidence,
        ),
        "liquidity_heatmap": liquidity_heatmap["summary"],
        "overlays": overlay_zones,
        "synthetic_markers": synthetic_markers,
        "trailing_stop": trailing,
        "render_hints": {
            "preferred_fps": 60,
            "realtime_source": "websocket_with_rest_fallback",
            "existing_markers": len(existing_markers or []),
            "volume_ratio": round(volume_ratio, 4),
            "layers": ["grid", "volume", "heatmap", "dom_ladder", "overlays", "candles", "markers", "execution_guide", "crosshair"],
            "heatmap_layer": True,
            "dom_ladder_layer": True,
            "gpu_overlay_batching": True,
            "shader_pipeline": {
                "heatmap": "fragment_gradient_tile_v1",
                "overlay_batching": "path_cache_mesh_reuse_v1",
                "low_power_fps": 30,
                "thermal_safe": True,
            },
            "render_profile": render_profile,
            "max_visible_candles": 140,
            "crosshair_repaint_isolated": True,
            "cache_key_inputs": ["symbol", "interval", "assistant_mode", "limit"],
        },
        "latest_candle": _candle_payload(latest),
    }


def _prepare_frame(frame: pd.DataFrame | None) -> pd.DataFrame:
    if frame is None or getattr(frame, "empty", True):
        return pd.DataFrame()
    working = frame.copy()
    for column in ("open", "high", "low", "close", "volume"):
        working[column] = working[column].astype(float)
    if "close_time" not in working.columns and "open_time" in working.columns:
        working["close_time"] = working["open_time"]
    return working.reset_index(drop=True)


def _empty_payload(*, symbol: str, interval: str, assistant_mode: str) -> dict[str, Any]:
    return {
        "chart_engine": "custom_canvas_pro",
        "scalp_engine": {
            "optimized_intervals": list(SCALP_INTERVALS),
            "active_interval": interval,
            "scalp_score": 0.0,
            "dominant_setup": "Adaptive Micro Flow",
        },
        "opportunity": {
            "confidence": 0.0,
            "expected_rr": 0.0,
            "momentum_score": 0.0,
            "volatility_score": 0.0,
            "whale_pressure": 0.0,
            "trend_strength": 0.0,
            "scalp_score": 0.0,
        },
        "market_regime": {
            "state": "RANGING",
            "confidence": 0.0,
            "summary": f"{symbol} is waiting for cleaner structure.",
        },
        "advanced_market_regime": {
            "state": "UNKNOWN",
            "confidence": 0.0,
            "transition_probability": 0.0,
            "strategy_suitability": {},
            "ai_modifiers": {"risk_multiplier": 0.0, "assistant_bias": "WAIT"},
            "reasons": ["insufficient_candles"],
        },
        "assistant_modes": list(ASSISTANT_MODES),
        "active_assistant_mode": _normalize_mode(assistant_mode),
        "execution_guide": {
            "side": "BUY",
            "entry_zone": {"low": 0.0, "high": 0.0},
            "stop_loss": 0.0,
            "tp1": 0.0,
            "tp2": 0.0,
            "trailing_stop_path": [],
            "risk_reward": 0.0,
            "risk_visualization": {"risk_pct": 0.0, "reward_pct": 0.0},
        },
        "strategy_state": {
            "active_strategy": "ADAPTIVE_SCALP_ENGINE",
            "active_timeframe": interval,
            "learns_from_successful_trades": False,
            "current_win_rate": 0.0,
            "promoted_strategies": [],
            "micro_strategies": [],
            "best_regime": "RANGING",
        },
        "ai_feed": [],
        "smc": {
            "structures": [],
            "confluence_score": 0.0,
            "breakout_strength": 0.0,
            "premium_discount": {"zone": "UNKNOWN", "discount_pct": 0.0, "premium_pct": 0.0},
            "summary": f"{symbol} has no structure payload yet.",
        },
        "ai_confidence_engine": {
            "confidence_score": 0.0,
            "risk_score": 0.0,
            "setup_quality": "WAIT",
            "trade_probability": 0.0,
            "factors": {},
            "invalidation_reasoning": ["No candles available for confidence scoring."],
            "explanation": "AI is waiting for candle data before assigning directional confidence.",
        },
        "orderflow": {
            "liquidity_pressure_score": 0.0,
            "directional_aggression_score": 0.0,
            "trap_probability": 0.0,
            "absorption_zones": [],
            "execution_quality": {"state": "NO_DATA"},
            "momentum": 0.0,
            "reasons": ["no market frame"],
        },
        "orderbook_depth": {
            "sequence_id": 0,
            "liquidity_ladder": [],
            "pressure_score": 0.0,
            "imbalance_probability": 0.0,
            "hidden_liquidity_score": 0.0,
            "exhaustion_warning": False,
            "spoofing_alerts": [],
            "iceberg_alerts": [],
            "execution_quality": {"state": "NO_DATA"},
        },
        "multi_agent_intelligence": {
            "consensus_score": 0.0,
            "adaptive_confidence": 0.0,
            "disagreement_score": 0.0,
            "direction": "WAIT",
            "votes": [],
        },
        "predictive_intelligence": {
            "breakout_probability": 0.0,
            "liquidity_target_zones": [],
            "exhaustion_probability": 0.0,
            "fakeout_probability": 0.0,
            "volatility_expansion_probability": 0.0,
            "trend_continuation_likelihood": 0.0,
            "confidence_cones": [],
        },
        "advanced_risk_intelligence": {
            "dynamic_size_multiplier": 0.0,
            "risk_state": "NO_DATA",
            "cooldown_seconds": 0,
            "warnings": [],
            "execution_note": "Advisory only. Final order routing still requires existing risk engine approval.",
        },
        "autonomous_assistant": {
            "symbol": symbol.upper(),
            "mode": "ASSISTED",
            "summary": f"{symbol} is waiting for enough data.",
            "recommendations": ["Wait for candle, liquidity, and regime confirmation."],
            "voice_alert": "No high quality setup yet.",
            "replay_safe": True,
        },
        "multi_timeframe_intelligence": {
            "execution_1m": "WAIT",
            "structure_5m": "WAIT",
            "momentum_15m": "WAIT",
            "bias_1h": "WAIT",
            "global_market_bias": "NEUTRAL",
            "scalp_opportunity_score": 0.0,
            "swing_opportunity_score": 0.0,
        },
        "liquidity_heatmap": {"zones": [], "heatmap_zones": [], "pressure_score": 0.0},
        "overlays": [],
        "synthetic_markers": [],
        "trailing_stop": {
            "mode": "ATR_TRAIL",
            "current_stop": 0.0,
            "projected_stop": 0.0,
            "path": [],
        },
        "render_hints": {
            "preferred_fps": 60,
            "realtime_source": "websocket_with_rest_fallback",
            "existing_markers": 0,
            "volume_ratio": 0.0,
            "layers": ["grid", "volume", "heatmap", "dom_ladder", "overlays", "candles", "markers", "execution_guide", "crosshair"],
            "heatmap_layer": True,
            "dom_ladder_layer": True,
            "gpu_overlay_batching": True,
            "shader_pipeline": {
                "heatmap": "fragment_gradient_tile_v1",
                "overlay_batching": "path_cache_mesh_reuse_v1",
                "low_power_fps": 30,
                "thermal_safe": True,
            },
            "render_profile": {
                "mode": "LOW_POWER",
                "target_fps": 30,
                "pressure": 0.0,
                "max_overlays": 18,
                "max_dom_levels": 8,
                "shader_quality": "reduced",
                "thermal_safe": True,
            },
            "max_visible_candles": 140,
            "crosshair_repaint_isolated": True,
            "cache_key_inputs": ["symbol", "interval", "assistant_mode", "limit"],
        },
        "latest_candle": None,
    }


def _market_regime(
    *,
    closes: pd.Series,
    highs: pd.Series,
    lows: pd.Series,
    volumes: pd.Series,
    volatility: float,
    volume_ratio: float,
    spread_bps: float,
    ema_fast: float,
    ema_slow: float,
) -> dict[str, Any]:
    price = float(closes.iloc[-1] or 0.0)
    slope = (float(closes.iloc[-1]) - float(closes.iloc[0])) / max(price, 1e-8)
    range_ratio = (float(highs.max()) - float(lows.min())) / max(price, 1e-8)
    direction_bias = abs(ema_fast - ema_slow) / max(price, 1e-8)
    chop = _chop_score(closes)
    if volume_ratio < 0.75 or spread_bps >= 18.0:
        state = "LOW_LIQUIDITY"
        confidence = _clamp(0.55 + (0.25 * (1.0 - min(volume_ratio, 1.0))), 0.0, 1.0)
        summary = "Liquidity is thin. Slippage protection should dominate execution."
    elif volatility >= 0.028 or range_ratio >= 0.04:
        state = "HIGH_VOLATILITY"
        confidence = _clamp(0.58 + min(volatility / 0.05, 0.28), 0.0, 1.0)
        summary = "Volatility expansion is active. Faster scalp reactions are favored."
    elif direction_bias >= 0.0025 and abs(slope) >= 0.003:
        state = "TRENDING"
        confidence = _clamp(0.56 + min(direction_bias * 140, 0.34), 0.0, 1.0)
        summary = "Trend alignment is strong enough for continuation-style scalps."
    elif chop >= 0.55:
        state = "CHOPPY"
        confidence = _clamp(0.50 + (chop * 0.35), 0.0, 1.0)
        summary = "The tape is choppy. Mean-reversion and tighter stops are safer."
    else:
        state = "RANGING"
        confidence = _clamp(0.48 + min(range_ratio * 8, 0.28), 0.0, 1.0)
        summary = "Price is rotating inside a range. Breakout confirmation matters more."
    return {
        "state": state,
        "confidence": round(confidence * 100, 2),
        "summary": summary,
    }


def _trailing_payload(
    *,
    side: str,
    current_price: float,
    stop_loss: float,
    atr: float,
    ema_anchor: float,
    volatility: float,
    interval: str,
) -> dict[str, Any]:
    atr_stop = current_price - (atr * 1.8) if side == "BUY" else current_price + (atr * 1.8)
    ema_stop = ema_anchor - (atr * 0.6) if side == "BUY" else ema_anchor + (atr * 0.6)
    adaptive_buffer = max(atr * 1.15, current_price * max(volatility, 0.0025))
    adaptive_stop = current_price - adaptive_buffer if side == "BUY" else current_price + adaptive_buffer
    volatility_stop = current_price - (current_price * max(volatility, 0.003)) if side == "BUY" else current_price + (current_price * max(volatility, 0.003))
    mode = "EMA_TRAIL" if interval == "1m" else "ADAPTIVE_TRAIL" if interval == "3m" else "ATR_TRAIL"
    current_stop = {
        "ATR_TRAIL": atr_stop,
        "EMA_TRAIL": ema_stop,
        "ADAPTIVE_TRAIL": adaptive_stop,
        "VOLATILITY_TRAIL": volatility_stop,
    }.get(mode, atr_stop)
    projected_stop = max(current_stop, stop_loss) if side == "BUY" else min(current_stop, stop_loss)
    path = [
        {"label": "initial", "price": round(stop_loss, 8)},
        {"label": "atr", "price": round(atr_stop, 8)},
        {"label": "ema", "price": round(ema_stop, 8)},
        {"label": "adaptive", "price": round(adaptive_stop, 8)},
        {"label": "volatility", "price": round(volatility_stop, 8)},
        {"label": "projected", "price": round(projected_stop, 8)},
    ]
    return {
        "mode": mode,
        "current_stop": round(current_stop, 8),
        "projected_stop": round(projected_stop, 8),
        "path": path,
    }


def _smc_payload(
    *,
    recent: pd.DataFrame,
    side: str,
    current_price: float,
    atr: float,
    confidence: float,
    trend_strength: float,
    momentum_score: float,
    volume_ratio: float,
    sweep_up: bool,
    sweep_down: bool,
    trend_shift: bool,
) -> dict[str, Any]:
    if recent.empty:
        return {
            "structures": [],
            "overlays": [],
            "markers": [],
            "confluence_score": 0.0,
            "breakout_strength": 0.0,
            "premium_discount": {"zone": "UNKNOWN", "discount_pct": 0.0, "premium_pct": 0.0},
            "summary": "No candles available for SMC detection.",
        }
    highs = recent["high"].astype(float)
    lows = recent["low"].astype(float)
    closes = recent["close"].astype(float)
    latest = recent.iloc[-1]
    lookback = recent.tail(min(len(recent), 24))
    prior = recent.iloc[:-1].tail(min(max(len(recent) - 1, 0), 16))
    prior_high = float(prior["high"].max()) if not prior.empty else float(highs.max())
    prior_low = float(prior["low"].min()) if not prior.empty else float(lows.min())
    range_high = float(lookback["high"].max())
    range_low = float(lookback["low"].min())
    range_size = max(range_high - range_low, 1e-8)
    premium_pct = _clamp((current_price - ((range_low + range_high) / 2)) / range_size, 0.0, 1.0)
    discount_pct = _clamp((((range_low + range_high) / 2) - current_price) / range_size, 0.0, 1.0)
    pd_zone = "DISCOUNT" if current_price < (range_low + range_high) / 2 else "PREMIUM"
    breakout_up = float(latest["close"]) > prior_high
    breakout_down = float(latest["close"]) < prior_low
    bos = breakout_up or breakout_down
    choch = trend_shift and not bos
    fvg = _fair_value_gap(recent, side=side, confidence=confidence)
    order_block = _order_block_zone(recent, side=side, confidence=confidence, atr=atr)

    structures: list[dict[str, Any]] = []
    overlays: list[dict[str, Any]] = []
    markers: list[dict[str, Any]] = []

    if bos:
        bos_side = "BUY" if breakout_up else "SELL"
        price = prior_high if breakout_up else prior_low
        structures.append(
            _structure_payload(
                structure_type="BOS",
                label="Break Of Structure",
                side=bos_side,
                price=price,
                timestamp_ms=_ts_ms(latest),
                confidence=max(confidence, trend_strength, 0.58),
                explanation=f"{bos_side} close displaced beyond the prior external structure.",
            )
        )
        markers.append(
            _structure_marker(
                marker_type="BOS",
                side=bos_side,
                price=price,
                timestamp_ms=_ts_ms(latest),
                confidence=max(confidence, trend_strength, 0.58),
                message="Break of structure confirmed by close beyond prior swing.",
            )
        )
    if choch:
        structures.append(
            _structure_payload(
                structure_type="CHOCH",
                label="Change Of Character",
                side=side,
                price=current_price,
                timestamp_ms=_ts_ms(latest),
                confidence=max(confidence * 0.78, 0.54),
                explanation="Fast structure changed direction before a confirmed external break.",
            )
        )
    if sweep_up or sweep_down:
        sweep_side = "SELL" if sweep_up else "BUY"
        structures.append(
            _structure_payload(
                structure_type="LIQUIDITY_SWEEP",
                label="Liquidity Sweep",
                side=sweep_side,
                price=float(latest["high"] if sweep_up else latest["low"]),
                timestamp_ms=_ts_ms(latest),
                confidence=max(confidence, 0.62),
                explanation="Wick cleared nearby liquidity and closed back inside the structure.",
            )
        )
    if fvg:
        structures.append(fvg["structure"])
        overlays.append(fvg["overlay"])
    if order_block:
        structures.append(order_block["structure"])
        overlays.append(order_block["overlay"])

    overlays.append(
        _zone_payload(
            zone_type="premium_discount",
            label=pd_zone,
            start_ts=_ts_ms(lookback.iloc[0]),
            end_ts=_ts_ms(latest),
            low=range_low,
            high=range_high,
            confidence=max(0.45, confidence * 0.7),
            side="SELL" if pd_zone == "PREMIUM" else "BUY",
            style="accent",
        )
    )
    confluence = _clamp(
        (confidence * 0.30)
        + (trend_strength * 0.18)
        + (momentum_score * 0.18)
        + (min(volume_ratio, 2.0) / 2.0 * 0.14)
        + (0.12 if bos else 0.0)
        + (0.10 if sweep_up or sweep_down else 0.0)
        + (0.08 if fvg else 0.0),
        0.0,
        1.0,
    )
    breakout_strength = _clamp(abs(float(latest["close"]) - (prior_high if side == "BUY" else prior_low)) / max(atr * 3, 1e-8), 0.0, 1.0)
    summary = (
        "SMC confluence supports continuation."
        if bos and confluence >= 0.65
        else "SMC confluence is forming but still needs confirmation."
        if structures
        else "No high-grade SMC structure is confirmed on the active window."
    )
    return {
        "structures": structures,
        "overlays": overlays,
        "markers": markers,
        "confluence_score": round(confluence * 100, 2),
        "breakout_strength": breakout_strength,
        "premium_discount": {
            "zone": pd_zone,
            "discount_pct": round(discount_pct * 100, 2),
            "premium_pct": round(premium_pct * 100, 2),
            "range_low": round(range_low, 8),
            "range_high": round(range_high, 8),
        },
        "summary": summary,
    }


def _fair_value_gap(recent: pd.DataFrame, *, side: str, confidence: float) -> dict[str, Any] | None:
    if len(recent) < 3:
        return None
    left = recent.iloc[-3]
    right = recent.iloc[-1]
    bullish_gap = float(left["high"]) < float(right["low"])
    bearish_gap = float(left["low"]) > float(right["high"])
    if not bullish_gap and not bearish_gap:
        return None
    gap_side = "BUY" if bullish_gap else "SELL"
    low = float(left["high"] if bullish_gap else right["high"])
    high = float(right["low"] if bullish_gap else left["low"])
    structure = _structure_payload(
        structure_type="FVG",
        label="Fair Value Gap",
        side=gap_side,
        price=(low + high) / 2,
        timestamp_ms=_ts_ms(right),
        confidence=max(confidence * 0.82, 0.52),
        explanation="Three-candle displacement left an inefficient price gap.",
    )
    overlay = _zone_payload(
        zone_type="fair_value_gap",
        label="FVG",
        start_ts=_ts_ms(left),
        end_ts=_ts_ms(right),
        low=low,
        high=high,
        confidence=max(confidence * 0.82, 0.52),
        side=gap_side if side in {"BUY", "SELL"} else gap_side,
        style="accent",
    )
    return {"structure": structure, "overlay": overlay}


def _order_block_zone(recent: pd.DataFrame, *, side: str, confidence: float, atr: float) -> dict[str, Any] | None:
    if len(recent) < 5:
        return None
    candles = list(recent.tail(min(len(recent), 12)).to_dict(orient="records"))
    target = None
    for row in reversed(candles[:-1]):
        bullish = float(row["close"]) >= float(row["open"])
        if side == "BUY" and not bullish:
            target = row
            break
        if side == "SELL" and bullish:
            target = row
            break
    if target is None:
        return None
    low = float(target["low"])
    high = float(target["high"])
    if high - low > max(atr * 2.8, 1e-8):
        midpoint = (low + high) / 2
        low = midpoint - atr
        high = midpoint + atr
    timestamp_ms = int(target.get("close_time", target.get("open_time", 0)) or 0)
    structure = _structure_payload(
        structure_type="ORDER_BLOCK",
        label="Order Block",
        side=side,
        price=(low + high) / 2,
        timestamp_ms=timestamp_ms,
        confidence=max(confidence * 0.72, 0.48),
        explanation="Last opposing candle before displacement is marked as a reaction zone.",
    )
    overlay = _zone_payload(
        zone_type="order_block",
        label="Order Block",
        start_ts=timestamp_ms,
        end_ts=_ts_ms(recent.iloc[-1]),
        low=low,
        high=high,
        confidence=max(confidence * 0.72, 0.48),
        side=side,
        style="bullish" if side == "BUY" else "bearish",
    )
    return {"structure": structure, "overlay": overlay}


def _structure_payload(
    *,
    structure_type: str,
    label: str,
    side: str,
    price: float,
    timestamp_ms: int,
    confidence: float,
    explanation: str,
) -> dict[str, Any]:
    return {
        "type": structure_type,
        "label": label,
        "side": side,
        "price": round(price, 8),
        "timestamp": _ts_iso(timestamp_ms),
        "confidence": round(_clamp(confidence, 0.0, 1.0) * 100, 2),
        "explanation": explanation,
    }


def _structure_marker(
    *,
    marker_type: str,
    side: str,
    price: float,
    timestamp_ms: int,
    confidence: float,
    message: str,
) -> dict[str, Any]:
    return {
        "type": "overlay",
        "marker_type": marker_type,
        "marker_style": "outline",
        "side": side,
        "price": round(price, 8),
        "timestamp": _ts_iso(timestamp_ms),
        "confidence_score": round(_clamp(confidence, 0.0, 1.0), 8),
        "reason": marker_type.lower(),
        "message": message,
        "intent": "Confirm risk gates before execution.",
        "logic_tags": ["smc", marker_type.lower()],
        "risk_flags": {},
    }


def _ai_confidence_engine(
    *,
    signal: SignalResponse | None,
    regime: str,
    confidence: float,
    trend_strength: float,
    momentum_score: float,
    volatility_score: float,
    volume_ratio: float,
    spread_bps: float,
    smc_confluence: float,
    breakout_strength: float,
) -> dict[str, Any]:
    factors = {
        "trend_strength": trend_strength,
        "volatility": 1.0 - min(volatility_score, 1.0) if regime == "HIGH_VOLATILITY" else volatility_score,
        "momentum": momentum_score,
        "liquidity": _clamp(min(volume_ratio, 2.0) / 2.0 - (spread_bps / 100.0), 0.0, 1.0),
        "volume": _clamp(min(volume_ratio, 2.0) / 2.0, 0.0, 1.0),
        "candle_structure": _clamp((momentum_score * 0.55) + (trend_strength * 0.45), 0.0, 1.0),
        "market_regime": 0.82 if regime == "TRENDING" else 0.62 if regime in {"RANGING", "HIGH_VOLATILITY"} else 0.35,
        "higher_timeframe_alignment": _clamp((trend_strength * 0.70) + (confidence * 0.30), 0.0, 1.0),
        "smc_confluence": smc_confluence,
        "breakout_strength": breakout_strength,
    }
    weights = {
        "trend_strength": 0.14,
        "volatility": 0.08,
        "momentum": 0.12,
        "liquidity": 0.10,
        "volume": 0.08,
        "candle_structure": 0.10,
        "market_regime": 0.10,
        "higher_timeframe_alignment": 0.12,
        "smc_confluence": 0.11,
        "breakout_strength": 0.05,
    }
    weighted = sum(factors[key] * weights[key] for key in weights)
    trade_probability = float(signal.inference.trade_probability) if signal is not None else weighted
    risk_score = _clamp(
        (volatility_score * 0.34)
        + ((spread_bps / 30.0) * 0.28)
        + ((1.0 - factors["liquidity"]) * 0.24)
        + (0.14 if regime in {"LOW_LIQUIDITY", "CHOPPY"} else 0.0),
        0.0,
        1.0,
    )
    invalidation = []
    if spread_bps >= 18:
        invalidation.append("Spread is too wide for clean execution.")
    if regime == "LOW_LIQUIDITY":
        invalidation.append("Liquidity is thin; slippage risk is elevated.")
    if smc_confluence < 0.45:
        invalidation.append("SMC confluence is not strong enough yet.")
    if trade_probability < 0.55:
        invalidation.append("Trade probability is below the execution-quality floor.")
    if not invalidation:
        invalidation.append("Invalidate if price re-enters the order block without reclaim.")
    return {
        "confidence_score": round(weighted * 100, 2),
        "risk_score": round(risk_score * 100, 2),
        "setup_quality": "A" if weighted >= 0.78 and risk_score <= 0.45 else "B" if weighted >= 0.62 else "WAIT",
        "trade_probability": round(_clamp(trade_probability, 0.0, 1.0) * 100, 2),
        "factors": {key: round(value * 100, 2) for key, value in factors.items()},
        "invalidation_reasoning": invalidation,
        "explanation": _confidence_explanation(regime=regime, smc_confluence=smc_confluence, momentum_score=momentum_score, volume_ratio=volume_ratio),
    }


def _confidence_explanation(*, regime: str, smc_confluence: float, momentum_score: float, volume_ratio: float) -> str:
    reasons = []
    if smc_confluence >= 0.6:
        reasons.append("SMC structure is aligned")
    if momentum_score >= 0.65:
        reasons.append("momentum expansion is active")
    if volume_ratio >= 1.2:
        reasons.append("volume confirmation is present")
    reasons.append(f"market regime is {regime.lower()}")
    return "; ".join(reasons) + "."


def _multi_timeframe_intelligence(
    *,
    interval: str,
    side: str,
    trend_strength: float,
    momentum_score: float,
    smc_confluence: float,
    confidence: float,
) -> dict[str, Any]:
    directional = "BULLISH" if side == "BUY" else "BEARISH"
    execution = directional if interval in {"1m", "3m"} and momentum_score >= 0.55 else "WAIT"
    structure = directional if smc_confluence >= 0.50 else "NEUTRAL"
    momentum = directional if momentum_score >= 0.60 else "NEUTRAL"
    bias = directional if trend_strength >= 0.50 and confidence >= 0.55 else "NEUTRAL"
    scalp_score = _clamp((momentum_score * 0.34) + (smc_confluence * 0.33) + (confidence * 0.33), 0.0, 1.0)
    swing_score = _clamp((trend_strength * 0.42) + (smc_confluence * 0.30) + (confidence * 0.28), 0.0, 1.0)
    aligned = [execution, structure, momentum, bias].count(directional)
    return {
        "execution_1m": execution,
        "structure_5m": structure,
        "momentum_15m": momentum,
        "bias_1h": bias,
        "global_market_bias": directional if aligned >= 3 else "NEUTRAL",
        "scalp_opportunity_score": round(scalp_score * 100, 2),
        "swing_opportunity_score": round(swing_score * 100, 2),
    }


def _liquidity_heatmap(
    *,
    recent: pd.DataFrame,
    support: float,
    resistance: float,
    current_price: float,
    volume_ratio: float,
    confidence: float,
    orderflow_pressure: float = 0.0,
) -> dict[str, Any]:
    if recent.empty:
        return {"summary": {"zones": [], "heatmap_zones": [], "pressure_score": 0.0}, "overlays": []}
    latest = recent.iloc[-1]
    pressure = _clamp(
        (min(volume_ratio, 2.5) / 2.5 * 0.42)
        + (confidence * 0.34)
        + (orderflow_pressure * 0.24),
        0.0,
        1.0,
    )
    zones = [
        {
            "name": "bid_liquidity",
            "price": round(support, 8),
            "pressure": round(pressure * 100, 2),
        },
        {
            "name": "ask_liquidity",
            "price": round(resistance, 8),
            "pressure": round((1.0 - min(abs(current_price - resistance) / max(current_price, 1e-8), 1.0)) * 100, 2),
        },
    ]
    overlays = [
        _zone_payload(
            zone_type="liquidity_heatmap",
            label="Bid Liquidity",
            start_ts=_ts_ms(recent.iloc[max(0, len(recent) - 12)]),
            end_ts=_ts_ms(latest),
            low=support * 0.9985,
            high=support * 1.0015,
            confidence=max(0.45, pressure),
            side="BUY",
            style="bullish",
        ),
        _zone_payload(
            zone_type="liquidity_heatmap",
            label="Ask Liquidity",
            start_ts=_ts_ms(recent.iloc[max(0, len(recent) - 12)]),
            end_ts=_ts_ms(latest),
            low=resistance * 0.9985,
            high=resistance * 1.0015,
            confidence=max(0.45, pressure),
            side="SELL",
            style="bearish",
        ),
    ]
    heatmap_zones = [
        {
            "side": zone["side"],
            "label": zone["label"],
            "start_ts": zone["start_ts"],
            "end_ts": zone["end_ts"],
            "low": zone["low"],
            "high": zone["high"],
            "intensity": round(pressure * 100, 2),
            "opacity": round(0.10 + (pressure * 0.24), 4),
        }
        for zone in overlays
    ]
    return {
        "summary": {
            "zones": zones,
            "heatmap_zones": heatmap_zones,
            "pressure_score": round(pressure * 100, 2),
            "nearest_wall": "bid_liquidity" if abs(current_price - support) < abs(current_price - resistance) else "ask_liquidity",
        },
        "overlays": overlays,
    }


def _synthetic_markers(
    *,
    symbol: str,
    interval: str,
    recent: pd.DataFrame,
    side: str,
    confidence: float,
    support: float,
    resistance: float,
    sweep_up: bool,
    sweep_down: bool,
    trend_shift: bool,
) -> list[dict[str, Any]]:
    latest = recent.iloc[-1]
    latest_ts = _ts_iso(_ts_ms(latest))
    markers: list[dict[str, Any]] = []
    if sweep_up or sweep_down:
        markers.append(
            {
                "type": "overlay",
                "marker_type": "LIQUIDITY_SWEEP",
                "marker_style": "ghost",
                "side": "SELL" if sweep_up else "BUY",
                "price": round(float(latest["close"]), 8),
                "timestamp": latest_ts,
                "confidence_score": round(max(0.55, confidence), 8),
                "reason": "liquidity_sweep_completed",
                "message": f"Liquidity sweep completed on {symbol}",
                "intent": f"Watch {interval} reclaim after sweep",
                "logic_tags": ["liquidity_sweep", interval],
                "risk_flags": {"liquidity_warning": False},
            }
        )
    if trend_shift:
        markers.append(
            {
                "type": "overlay",
                "marker_type": "TREND_SHIFT",
                "marker_style": "outline",
                "side": side,
                "price": round(float(latest["close"]), 8),
                "timestamp": latest_ts,
                "confidence_score": round(max(0.56, confidence), 8),
                "reason": "trend_shift_detected",
                "message": f"Trend shift marker printed on {symbol}",
                "intent": "Scale into momentum only after confirmation",
                "logic_tags": ["trend_shift", interval],
                "risk_flags": {"trend_shift": True},
            }
        )
    markers.append(
        {
            "type": "overlay",
            "marker_type": "SUPPORT",
            "marker_style": "ghost",
            "side": "BUY",
            "price": round(support, 8),
            "timestamp": latest_ts,
            "confidence_score": round(max(0.45, confidence * 0.8), 8),
            "reason": "support_detected",
            "message": "Support shelf reinforced by recent lows",
            "intent": "Aggressive longs only above support retention",
            "logic_tags": ["support", interval],
            "risk_flags": {},
        }
    )
    markers.append(
        {
            "type": "overlay",
            "marker_type": "RESISTANCE",
            "marker_style": "ghost",
            "side": "SELL",
            "price": round(resistance, 8),
            "timestamp": latest_ts,
            "confidence_score": round(max(0.45, confidence * 0.8), 8),
            "reason": "resistance_detected",
            "message": "Resistance shelf reinforced by recent highs",
            "intent": "Breakout longs need clean resistance acceptance",
            "logic_tags": ["resistance", interval],
            "risk_flags": {},
        }
    )
    return markers


def _micro_strategies(
    *,
    scalp_score: float,
    confidence: float,
    momentum_score: float,
    volume_ratio: float,
    sweep_up: bool,
    sweep_down: bool,
    trend_shift: bool,
    regime: str,
) -> list[dict[str, Any]]:
    strategies = [
        {
            "name": "Momentum Ignition",
            "score": round(_clamp((momentum_score * 0.55) + (confidence * 0.45), 0.0, 1.0) * 100, 2),
            "state": "PROMOTED" if momentum_score >= 0.7 else "WATCH",
        },
        {
            "name": "Breakout Compression",
            "score": round(_clamp((scalp_score * 0.55) + (min(volume_ratio, 2.0) / 2.0 * 0.45), 0.0, 1.0) * 100, 2),
            "state": "PROMOTED" if volume_ratio >= 1.25 else "WATCH",
        },
        {
            "name": "Liquidity Sweep Reclaim",
            "score": round((0.82 if sweep_up or sweep_down else max(0.35, confidence * 0.55)) * 100, 2),
            "state": "PROMOTED" if sweep_up or sweep_down else "SHADOW",
        },
        {
            "name": "Trend Shift Pullback",
            "score": round((0.80 if trend_shift else max(0.40, scalp_score * 0.72)) * 100, 2),
            "state": "PROMOTED" if trend_shift and regime in {"TRENDING", "HIGH_VOLATILITY"} else "WATCH",
        },
    ]
    strategies.sort(key=lambda item: float(item["score"]), reverse=True)
    return strategies


def _ai_feed(
    *,
    symbol: str,
    regime: str,
    confidence: float,
    scalp_score: float,
    sweep_up: bool,
    sweep_down: bool,
    trend_shift: bool,
    momentum_score: float,
    volume_ratio: float,
) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc).isoformat()
    items = []
    if momentum_score >= 0.68:
        items.append(
            {
                "title": f"Momentum ignition detected on {symbol}",
                "detail": "Short-term impulse and order-flow alignment improved materially.",
                "severity": "high",
                "timestamp": now,
            }
        )
    if sweep_up or sweep_down:
        items.append(
            {
                "title": "Liquidity sweep completed",
                "detail": "The latest wick ran external liquidity and closed back inside structure.",
                "severity": "high",
                "timestamp": now,
            }
        )
    if volume_ratio >= 1.18 and regime in {"RANGING", "TRENDING"}:
        items.append(
            {
                "title": "Breakout compression forming",
                "detail": "Compression plus expanding volume is building a short-term breakout candidate.",
                "severity": "medium",
                "timestamp": now,
            }
        )
    if scalp_score >= 0.72 or confidence >= 0.72:
        items.append(
            {
                "title": "High probability scalp forming",
                "detail": "AI confluence is above the short-term execution floor.",
                "severity": "high",
                "timestamp": now,
            }
        )
    if trend_shift:
        items.append(
            {
                "title": "Trend shift marker printed",
                "detail": "Fast/slow EMA structure changed direction on the active tape.",
                "severity": "medium",
                "timestamp": now,
            }
        )
    if not items:
        items.append(
            {
                "title": f"{symbol} is still building structure",
                "detail": "AI is waiting for better momentum, liquidity, or trend clarity.",
                "severity": "low",
                "timestamp": now,
            }
        )
    return items[:4]


def _confidence_score(signal: SignalResponse | None, momentum_score: float, trend_strength: float) -> float:
    if signal is not None:
        return _clamp(float(signal.inference.confidence_score), 0.0, 1.0)
    return _clamp((momentum_score * 0.55) + (trend_strength * 0.45), 0.0, 1.0)


def _whale_pressure(signal: SignalResponse | None) -> float:
    if signal is None:
        return 0.5
    accumulation = float(signal.alpha.whale.accumulation_score or 0.0)
    unusual = float(signal.alpha.whale.unusual_activity_score or 0.0)
    return _clamp((accumulation * 0.7) + ((1.0 - unusual) * 0.3), 0.0, 1.0)


def _decision_side(signal: SignalResponse | None, ema_fast: float, ema_slow: float) -> str:
    if signal is not None and signal.inference.decision in {"BUY", "SELL"}:
        return signal.inference.decision
    return "BUY" if ema_fast >= ema_slow else "SELL"


def _expected_rr(*, entry: float, stop_loss: float, take_profit: float) -> float:
    risk = abs(entry - stop_loss)
    reward = abs(take_profit - entry)
    if risk <= 0:
        return 0.0
    return reward / risk


def _zone_payload(
    *,
    zone_type: str,
    label: str,
    start_ts: int,
    end_ts: int,
    low: float,
    high: float,
    confidence: float,
    side: str,
    style: str,
) -> dict[str, Any]:
    ttl_minutes = 20 if zone_type in {"fair_value_gap", "liquidity_sweep", "trend_shift"} else 60
    priority = {
        "liquidity_sweep": 90,
        "fair_value_gap": 80,
        "order_block": 78,
        "premium_discount": 55,
        "take_profit_zone": 50,
        "stop_loss_zone": 50,
    }.get(zone_type, 40)
    return {
        "zone_type": zone_type,
        "label": label,
        "start_ts": int(start_ts),
        "end_ts": int(end_ts),
        "low": round(min(low, high), 8),
        "high": round(max(low, high), 8),
        "confidence": round(_clamp(confidence, 0.0, 1.0) * 100, 2),
        "side": side,
        "style": style,
        "priority": priority,
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)).isoformat(),
    }


def _candle_payload(row: pd.Series) -> dict[str, Any]:
    return {
        "timestamp": _ts_ms(row),
        "open": round(float(row["open"]), 8),
        "high": round(float(row["high"]), 8),
        "low": round(float(row["low"]), 8),
        "close": round(float(row["close"]), 8),
        "volume": round(float(row["volume"]), 8),
    }


def _ts_ms(row: pd.Series) -> int:
    return int(row.get("close_time", row.get("open_time", 0)) or 0)


def _ts_iso(timestamp_ms: int) -> str:
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).isoformat()


def _atr(frame: pd.DataFrame) -> float:
    if frame.empty or len(frame) < 2:
        return 0.0
    highs = frame["high"].astype(float)
    lows = frame["low"].astype(float)
    closes = frame["close"].astype(float)
    prev_close = closes.shift(1)
    true_range = pd.concat(
        [
            (highs - lows).abs(),
            (highs - prev_close).abs(),
            (lows - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return float(true_range.tail(min(len(true_range), 14)).mean() or 0.0)


def _chop_score(closes: pd.Series) -> float:
    if len(closes) < 4:
        return 0.0
    deltas = closes.diff().dropna()
    if deltas.empty:
        return 0.0
    sign_changes = 0
    previous_sign = 0
    for delta in deltas:
        sign = 1 if delta > 0 else -1 if delta < 0 else 0
        if previous_sign != 0 and sign != 0 and sign != previous_sign:
            sign_changes += 1
        if sign != 0:
            previous_sign = sign
    return _clamp(sign_changes / max(len(deltas), 1), 0.0, 1.0)


def _normalize_mode(mode: str) -> str:
    candidate = str(mode or "ASSISTED").upper().replace(" ", "_")
    return candidate if candidate in ASSISTANT_MODES else "ASSISTED"


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))
