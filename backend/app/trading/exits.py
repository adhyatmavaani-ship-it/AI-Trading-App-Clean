from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.core.config import Settings


@dataclass(frozen=True)
class InitialExitPlan:
    stop_loss: float
    trailing_stop_pct: float
    take_profit: float
    stop_distance: float


@dataclass(frozen=True)
class ExitEvaluation:
    action: str
    exit_reason: str
    exit_type: str
    stop_loss: float
    trailing_stop_pct: float
    take_profit: float
    partial_close_fraction: float = 0.0
    partial_take_profit_taken: bool = False


def initial_exit_plan(
    *,
    side: str,
    entry_price: float,
    atr: float,
    volatility: float,
    stop_loss_multiplier: float = 1.0,
    take_profit_rr: float = 1.5,
    atr_stop_multiplier: float = 1.8,
    min_stop_pct: float = 0.006,
    trailing_atr_multiplier: float = 2.2,
    min_trailing_pct: float = 0.0025,
    max_trailing_pct: float = 0.05,
) -> InitialExitPlan:
    normalized_side = str(side or "HOLD").upper()
    stop_distance = max(
        float(atr) * float(atr_stop_multiplier) * float(stop_loss_multiplier),
        float(entry_price) * float(min_stop_pct),
        float(entry_price) * max(float(volatility), 0.0),
    )
    if normalized_side == "BUY":
        stop_loss = float(entry_price) - stop_distance
        take_profit = float(entry_price) + (stop_distance * float(take_profit_rr))
    else:
        stop_loss = float(entry_price) + stop_distance
        take_profit = float(entry_price) - (stop_distance * float(take_profit_rr))
    trailing_stop_pct = max(
        float(min_trailing_pct),
        min(
            float(max_trailing_pct),
            (float(trailing_atr_multiplier) * float(atr) * float(stop_loss_multiplier))
            / max(float(entry_price), 1e-8),
        ),
    )
    return InitialExitPlan(
        stop_loss=round(float(stop_loss), 8),
        trailing_stop_pct=round(float(trailing_stop_pct), 6),
        take_profit=round(float(take_profit), 8),
        stop_distance=round(float(stop_distance), 8),
    )


def compute_trailing_multiplier(
    *,
    settings: Settings,
    volatility: float,
    regime: str,
    adx: float = 0.0,
    adaptive_value: float = 1.0,
) -> float:
    multiplier = float(adaptive_value)
    if float(volatility) >= 0.03:
        multiplier *= 1.1
    if str(regime or "").upper() != "TRENDING" or float(adx) < float(settings.strict_trade_structure_adx_floor):
        multiplier *= 0.9
    return max(0.5, min(multiplier, 1.5))


def strong_opposite_candle(
    *,
    side: str,
    frame: pd.DataFrame | None,
    atr: float,
    threshold: float,
) -> bool:
    if frame is None or len(frame) < 1 or float(atr) <= 0:
        return False
    candle = frame.iloc[-1]
    open_price = float(candle["open"])
    close_price = float(candle["close"])
    body = abs(close_price - open_price)
    normalized_side = str(side or "").upper()
    opposite_direction = (
        (normalized_side == "BUY" and close_price < open_price)
        or (normalized_side == "SELL" and close_price > open_price)
    )
    return opposite_direction and body >= (float(atr) * float(threshold))


def volume_spike_against_trade(
    *,
    side: str,
    frame: pd.DataFrame | None,
    threshold: float,
) -> bool:
    if frame is None or len(frame) < 3:
        return False
    volume = frame["volume"].astype(float)
    baseline = float(volume.tail(20).mean() or 0.0)
    current_volume = float(volume.iloc[-1])
    if current_volume < baseline * float(threshold):
        return False
    candle = frame.iloc[-1]
    open_price = float(candle["open"])
    close_price = float(candle["close"])
    normalized_side = str(side or "").upper()
    return (
        (normalized_side == "BUY" and close_price < open_price)
        or (normalized_side == "SELL" and close_price > open_price)
    )


def evaluate_exit(
    *,
    settings: Settings,
    trade: dict,
    latest_price: float,
    atr: float,
    regime: str,
    volatility: float,
    frame: pd.DataFrame | None,
    trailing_multiplier: float,
    structure_break: bool = False,
    stop_hit: bool | None = None,
) -> ExitEvaluation:
    side = str(trade.get("side", "") or "").upper()
    entry = float(trade.get("entry", 0.0) or 0.0)
    old_stop = float(trade.get("stop_loss", 0.0) or 0.0)
    take_profit = float(trade.get("take_profit", 0.0) or 0.0)
    initial_stop = float(trade.get("initial_stop_loss", old_stop) or old_stop)
    initial_risk = abs(entry - initial_stop)
    partial_taken = bool(trade.get("partial_take_profit_taken", False))

    updated_stop = old_stop
    if entry > 0 and float(atr) > 0:
        profit_distance = (float(latest_price) - entry) if side == "BUY" else (entry - float(latest_price))
        rr = profit_distance / max(initial_risk, 1e-8)
        if rr >= float(settings.active_trade_monitor_break_even_rr):
            locked_profit = float(settings.active_trade_monitor_break_even_lock_rr) * initial_risk
            breakeven_stop = entry + locked_profit if side == "BUY" else entry - locked_profit
            if side == "BUY":
                updated_stop = max(updated_stop, breakeven_stop)
            else:
                updated_stop = min(updated_stop, breakeven_stop) if updated_stop > 0 else breakeven_stop

        if side == "BUY":
            highest_high = float(frame["high"].astype(float).tail(10).max()) if frame is not None else float(latest_price)
            baseline_stop = highest_high - (2.5 * float(atr) * float(trailing_multiplier))
            updated_stop = max(updated_stop, baseline_stop)
        else:
            lowest_low = float(frame["low"].astype(float).tail(10).min()) if frame is not None else float(latest_price)
            baseline_stop = lowest_low + (2.5 * float(atr) * float(trailing_multiplier))
            updated_stop = min(updated_stop, baseline_stop) if updated_stop > 0 else baseline_stop
    else:
        rr = 0.0

    trailing_stop_pct = round((2.5 * float(atr) * float(trailing_multiplier)) / max(float(latest_price), 1e-8), 6) if float(atr) > 0 else float(trade.get("trailing_stop_pct", 0.0) or 0.0)

    adverse_reason = ""
    if structure_break:
        adverse_reason = "structure_break"
    elif strong_opposite_candle(
        side=side,
        frame=frame,
        atr=atr,
        threshold=float(settings.active_trade_monitor_opposite_candle_atr_threshold),
    ):
        adverse_reason = "momentum_reversal"
    elif volume_spike_against_trade(
        side=side,
        frame=frame,
        threshold=float(settings.active_trade_monitor_volume_spike_threshold),
    ):
        adverse_reason = "volume_reversal"

    if stop_hit is None:
        stop_hit = (
            (side == "BUY" and updated_stop > 0 and float(latest_price) <= updated_stop)
            or (side == "SELL" and updated_stop > 0 and float(latest_price) >= updated_stop)
        )

    if not partial_taken and entry > 0 and initial_risk > 0 and rr >= float(settings.strict_trade_partial_take_profit_rr):
        locked_profit = float(settings.active_trade_monitor_break_even_lock_rr) * initial_risk
        breakeven_stop = entry + locked_profit if side == "BUY" else entry - locked_profit
        if side == "BUY":
            updated_stop = max(updated_stop, breakeven_stop)
        else:
            updated_stop = min(updated_stop, breakeven_stop) if updated_stop > 0 else breakeven_stop
        return ExitEvaluation(
            action="partial_close",
            exit_reason="partial_take_profit",
            exit_type="partial_take_profit",
            stop_loss=round(float(updated_stop), 8),
            trailing_stop_pct=round(float(trailing_stop_pct), 6),
            take_profit=round(float(take_profit), 8),
            partial_close_fraction=0.4,
            partial_take_profit_taken=True,
        )

    if adverse_reason:
        if rr < 0.75 and not partial_taken:
            return ExitEvaluation(
                action="full_close",
                exit_reason=adverse_reason,
                exit_type="early_exit",
                stop_loss=round(float(updated_stop), 8),
                trailing_stop_pct=round(float(trailing_stop_pct), 6),
                take_profit=round(float(take_profit), 8),
                partial_take_profit_taken=partial_taken,
            )
        tighten_buffer = max(float(atr) * 0.8, initial_risk * 0.35, float(latest_price) * 0.0005)
        if side == "BUY":
            tightened_stop = min(float(latest_price) - max(float(latest_price) * 0.0005, 1e-8), float(latest_price) - tighten_buffer)
            updated_stop = max(updated_stop, tightened_stop)
        else:
            tightened_stop = max(float(latest_price) + max(float(latest_price) * 0.0005, 1e-8), float(latest_price) + tighten_buffer)
            updated_stop = min(updated_stop, tightened_stop) if updated_stop > 0 else tightened_stop

    if stop_hit:
        return ExitEvaluation(
            action="full_close",
            exit_reason="stop_loss_hit",
            exit_type="stop_loss",
            stop_loss=round(float(updated_stop), 8),
            trailing_stop_pct=round(float(trailing_stop_pct), 6),
            take_profit=round(float(take_profit), 8),
            partial_take_profit_taken=partial_taken,
        )

    return ExitEvaluation(
        action="hold",
        exit_reason="",
        exit_type="trailing",
        stop_loss=round(float(updated_stop), 8),
        trailing_stop_pct=round(float(trailing_stop_pct), 6),
        take_profit=round(float(take_profit), 8),
        partial_take_profit_taken=partial_taken,
    )
