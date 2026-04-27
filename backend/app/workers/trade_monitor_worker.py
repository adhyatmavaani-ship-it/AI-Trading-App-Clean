from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.core.config import Settings

if TYPE_CHECKING:
    from app.services.feature_pipeline import FeaturePipeline
    from app.services.market_data import MarketDataService
    from app.services.redis_state_manager import RedisStateManager
    from app.services.trading_orchestrator import TradingOrchestrator


logger = logging.getLogger(__name__)


@dataclass
class ActiveTradeMonitorWorker:
    settings: Settings
    redis_state_manager: RedisStateManager
    market_data: MarketDataService
    feature_pipeline: FeaturePipeline
    trading_orchestrator: TradingOrchestrator

    def __post_init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        if not self.settings.active_trade_monitor_enabled:
            return
        if self._task is not None and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop(), name="active-trade-monitor")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            try:
                await self._task
            finally:
                self._task = None

    async def run_once(self) -> None:
        monitored = self.redis_state_manager.restore_monitored_trades()
        active_by_id = {
            str(trade.get("trade_id", "") or ""): trade
            for trade in self.redis_state_manager.restore_active_trades()
        }
        for registered in monitored:
            trade_id = str(registered.get("trade_id", "") or "")
            if not trade_id:
                continue
            active_trade = active_by_id.get(trade_id)
            if active_trade is None:
                self.redis_state_manager.unregister_monitored_trade(trade_id)
                continue
            try:
                await self._analyze_trade(active_trade)
            except Exception as exc:  # pragma: no cover
                logger.warning(
                    "active_trade_monitor_trade_failed",
                    extra={
                        "event": "active_trade_monitor_trade_failed",
                        "context": {"trade_id": trade_id, "error": str(exc)[:200]},
                    },
                )

    async def _run_loop(self) -> None:
        interval = max(float(self.settings.active_trade_monitor_interval_seconds), 1.0)
        while not self._stop_event.is_set():
            await self.run_once()
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                continue

    async def _analyze_trade(self, trade: dict) -> None:
        trade_id = str(trade.get("trade_id", "") or "")
        user_id = str(trade.get("user_id", "") or "")
        symbol = str(trade.get("symbol", "") or "").upper()
        side = str(trade.get("side", "") or "").upper()
        if not trade_id or not user_id or side not in {"BUY", "SELL"}:
            return

        frames = await self.market_data.fetch_multi_timeframe_ohlcv(symbol, intervals=("5m", "15m", "1h"))
        order_book = await self.market_data.fetch_order_book(symbol)
        snapshot = self.feature_pipeline.build(symbol, frames, order_book)
        latest_price = float(snapshot.price)
        primary_frame = frames.get("5m")
        if primary_frame is None:
            primary_frame = frames.get("15m")

        await self._update_trailing_stop(trade=trade, snapshot=snapshot, latest_price=latest_price, frame=primary_frame)

        if self._structure_break_against_trade(trade=trade, snapshot=snapshot):
            self._close_trade(trade=trade, exit_price=latest_price, reason="structure_break", exit_type="early_exit")
            return
        if self._strong_opposite_candle(trade=trade, frame=primary_frame, snapshot=snapshot):
            self._close_trade(trade=trade, exit_price=latest_price, reason="momentum_reversal", exit_type="early_exit")
            return
        if self._volume_spike_against_trade(trade=trade, frame=primary_frame):
            self._close_trade(trade=trade, exit_price=latest_price, reason="volume_reversal", exit_type="early_exit")
            return

        stop_loss = float(trade.get("stop_loss", 0.0) or 0.0)
        if stop_loss > 0:
            if side == "BUY" and latest_price <= stop_loss:
                self._close_trade(trade=trade, exit_price=latest_price, reason="stop_loss_hit", exit_type="stop_loss")
            elif side == "SELL" and latest_price >= stop_loss:
                self._close_trade(trade=trade, exit_price=latest_price, reason="stop_loss_hit", exit_type="stop_loss")

    async def _update_trailing_stop(self, *, trade: dict, snapshot, latest_price: float, frame) -> None:
        trade_id = str(trade.get("trade_id", "") or "")
        side = str(trade.get("side", "") or "").upper()
        old_stop = float(trade.get("stop_loss", 0.0) or 0.0)
        atr = float(snapshot.atr or snapshot.features.get("15m_atr", snapshot.features.get("5m_atr", 0.0)) or 0.0)
        if atr <= 0:
            return

        entry = float(trade.get("entry", 0.0) or 0.0)
        initial_stop = float(trade.get("initial_stop_loss", old_stop) or old_stop)
        initial_risk = abs(entry - initial_stop)
        trailing_multiplier = self._trailing_multiplier(snapshot)
        if entry > 0 and initial_risk > 0:
            profit_distance = (latest_price - entry) if side == "BUY" else (entry - latest_price)
            if profit_distance > (float(self.settings.active_trade_monitor_break_even_rr) * initial_risk):
                locked_profit = float(self.settings.active_trade_monitor_break_even_lock_rr) * initial_risk
                breakeven_stop = entry + locked_profit if side == "BUY" else entry - locked_profit
                if side == "BUY":
                    old_stop = max(old_stop, breakeven_stop)
                else:
                    old_stop = min(old_stop, breakeven_stop) if old_stop > 0 else breakeven_stop

        if side == "BUY":
            highest_high = float(frame["high"].astype(float).tail(10).max()) if frame is not None else latest_price
            baseline = highest_high - (2.5 * atr * trailing_multiplier)
            new_stop = max(old_stop, baseline)
        else:
            lowest_low = float(frame["low"].astype(float).tail(10).min()) if frame is not None else latest_price
            baseline = lowest_low + (2.5 * atr * trailing_multiplier)
            new_stop = min(old_stop, baseline) if old_stop > 0 else baseline

        if old_stop > 0 and abs(new_stop - old_stop) < 1e-8:
            self._update_trade_metrics(trade=trade, latest_price=latest_price)
            return
        updated = dict(trade)
        updated["stop_loss"] = round(float(new_stop), 8)
        updated["trailing_stop_pct"] = round((2.5 * atr * trailing_multiplier) / max(latest_price, 1e-8), 6)
        updated["exit_type"] = "trailing"
        self._update_trade_metrics(trade=updated, latest_price=latest_price)
        self.trading_orchestrator.update_active_trade_state(trade_id, updated)

    def _update_trade_metrics(self, *, trade: dict, latest_price: float) -> None:
        entry = float(trade.get("entry", 0.0) or 0.0)
        side = str(trade.get("side", "") or "").upper()
        if entry <= 0 or side not in {"BUY", "SELL"}:
            return
        current_profit = ((latest_price - entry) / entry) if side == "BUY" else ((entry - latest_price) / entry)
        trade["max_profit"] = round(max(float(trade.get("max_profit", 0.0) or 0.0), current_profit), 8)

    def _structure_break_against_trade(self, *, trade: dict, snapshot) -> bool:
        side = str(trade.get("side", "") or "").upper()
        bearish = bool(float(snapshot.features.get("15m_structure_bearish", snapshot.features.get("5m_structure_bearish", 0.0)) or 0.0) >= 1.0)
        bullish = bool(float(snapshot.features.get("15m_structure_bullish", snapshot.features.get("5m_structure_bullish", 0.0)) or 0.0) >= 1.0)
        return (side == "BUY" and bearish) or (side == "SELL" and bullish)

    def _strong_opposite_candle(self, *, trade: dict, frame, snapshot) -> bool:
        if frame is None or len(frame) < 1:
            return False
        candle = frame.iloc[-1]
        open_price = float(candle["open"])
        close_price = float(candle["close"])
        body = abs(close_price - open_price)
        atr = float(snapshot.atr or snapshot.features.get("5m_atr", 0.0) or 0.0)
        if atr <= 0:
            return False
        side = str(trade.get("side", "") or "").upper()
        opposite_direction = (side == "BUY" and close_price < open_price) or (side == "SELL" and close_price > open_price)
        return opposite_direction and body >= (atr * float(self.settings.active_trade_monitor_opposite_candle_atr_threshold))

    def _volume_spike_against_trade(self, *, trade: dict, frame) -> bool:
        if frame is None or len(frame) < 3:
            return False
        volume = frame["volume"].astype(float)
        baseline = float(volume.tail(20).mean() or 0.0)
        current_volume = float(volume.iloc[-1])
        if current_volume < baseline * float(self.settings.active_trade_monitor_volume_spike_threshold):
            return False
        candle = frame.iloc[-1]
        open_price = float(candle["open"])
        close_price = float(candle["close"])
        side = str(trade.get("side", "") or "").upper()
        return (side == "BUY" and close_price < open_price) or (side == "SELL" and close_price > open_price)

    def _close_trade(self, *, trade: dict, exit_price: float, reason: str, exit_type: str) -> None:
        updated_trade = dict(trade)
        updated_trade["exit_reason"] = reason
        updated_trade["exit_type"] = exit_type
        self._update_trade_metrics(trade=updated_trade, latest_price=float(exit_price))
        self.trading_orchestrator.update_active_trade_state(str(updated_trade.get("trade_id", "") or ""), updated_trade)
        self.trading_orchestrator.close_trade_position(
            user_id=str(trade.get("user_id", "") or ""),
            trade_id=str(trade.get("trade_id", "") or ""),
            exit_price=float(exit_price),
            reason=reason,
            exit_fee=0.0,
        )

    def _trailing_multiplier(self, snapshot) -> float:
        cache = getattr(self.redis_state_manager, "cache", None)
        base = float(self.settings.trailing_aggressiveness)
        if cache is not None:
            adaptive = cache.get_json("strategy:adaptive_config:system") or {}
            base = float(adaptive.get("trailing_aggressiveness", base) or base)
        volatility = float(getattr(snapshot, "volatility", 0.0) or 0.0)
        regime = str(getattr(snapshot, "regime", "") or "").upper()
        adx = float(getattr(snapshot, "features", {}).get("15m_adx", getattr(snapshot, "features", {}).get("5m_adx", 0.0)) or 0.0)
        if volatility >= 0.03:
            base *= 1.1
        if regime != "TRENDING" or adx < float(self.settings.strict_trade_structure_adx_floor):
            base *= 0.9
        return max(0.5, min(base, 1.5))
