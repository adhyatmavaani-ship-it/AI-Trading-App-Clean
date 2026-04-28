from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.core.config import Settings
from app.trading.exits import compute_trailing_multiplier, evaluate_exit

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
        atr = float(snapshot.atr or snapshot.features.get("15m_atr", snapshot.features.get("5m_atr", 0.0)) or 0.0)
        trailing_multiplier = self._trailing_multiplier(snapshot)
        evaluation = evaluate_exit(
            settings=self.settings,
            trade=trade,
            latest_price=latest_price,
            atr=atr,
            regime=str(getattr(snapshot, "regime", "") or ""),
            volatility=float(getattr(snapshot, "volatility", 0.0) or 0.0),
            frame=primary_frame,
            trailing_multiplier=trailing_multiplier,
            structure_break=self._structure_break_against_trade(trade=trade, snapshot=snapshot),
        )
        updated = dict(trade)
        updated["stop_loss"] = float(evaluation.stop_loss)
        updated["trailing_stop_pct"] = float(evaluation.trailing_stop_pct)
        updated["take_profit"] = float(evaluation.take_profit)
        updated["partial_take_profit_taken"] = bool(
            trade.get("partial_take_profit_taken", False) or evaluation.partial_take_profit_taken
        )
        updated["exit_type"] = str(evaluation.exit_type or updated.get("exit_type", ""))
        self._update_trade_metrics(trade=updated, latest_price=latest_price)
        self.trading_orchestrator.update_active_trade_state(trade_id, updated)

        if (
            evaluation.action == "partial_close"
            and not bool(trade.get("partial_take_profit_taken", False))
        ):
            self.trading_orchestrator.close_trade_position(
                user_id=user_id,
                trade_id=trade_id,
                exit_price=latest_price,
                closed_quantity=float(trade.get("executed_quantity", 0.0) or 0.0)
                * float(self.settings.strict_trade_partial_take_profit_fraction),
                reason=evaluation.exit_reason,
            )
            return

        if (
            evaluation.action == "full_close"
            and bool(updated.get("partial_take_profit_taken", False))
            and evaluation.exit_type != "stop_loss"
        ):
            return

        if evaluation.action == "full_close":
            self._close_trade(
                trade=updated,
                exit_price=latest_price,
                reason=evaluation.exit_reason,
                exit_type=evaluation.exit_type,
            )

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
        return compute_trailing_multiplier(
            settings=self.settings,
            volatility=float(getattr(snapshot, "volatility", 0.0) or 0.0),
            regime=str(getattr(snapshot, "regime", "") or "").upper(),
            adx=float(
                getattr(snapshot, "features", {}).get(
                    "15m_adx",
                    getattr(snapshot, "features", {}).get("5m_adx", 0.0),
                )
                or 0.0
            ),
            adaptive_value=base,
        )
