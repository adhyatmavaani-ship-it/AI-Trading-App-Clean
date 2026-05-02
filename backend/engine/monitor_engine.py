from __future__ import annotations

import asyncio
import math

from db.database import SQLiteTradeDatabase
from models.trade import TradeRecord
from services.price_service import PriceService
from utils.logger import get_logger


class MarketPriceStore:
    def __init__(self) -> None:
        self._prices: dict[str, tuple[float, str]] = {}

    def set_price(self, symbol: str, price: float) -> None:
        self._prices[symbol.upper()] = (float(price), "manual")

    def get_price(self, symbol: str) -> tuple[float, str] | None:
        return self._prices.get(symbol.upper())

    def consume_prices(self, symbols: list[str]) -> dict[str, tuple[float, str]]:
        resolved: dict[str, tuple[float, str]] = {}
        for symbol in {item.upper() for item in symbols}:
            if symbol not in self._prices:
                continue
            resolved[symbol] = self._prices.pop(symbol)
        return resolved


def apply_slippage(price: float, side: str, slippage_bps: float, *, min_tick: float = 0.01) -> float:
    adjusted_tick = max(float(min_tick), 1e-8)
    slip = float(price) * (max(float(slippage_bps), 0.0) / 10_000.0)
    adjusted = float(price) + slip if side.upper() == "BUY" else float(price) - slip
    scaled = adjusted / adjusted_tick
    if side.upper() == "BUY":
        return math.ceil(scaled - 1e-9) * adjusted_tick
    return math.floor(scaled + 1e-9) * adjusted_tick


class MonitorEngine:
    def __init__(
        self,
        db: SQLiteTradeDatabase,
        *,
        cache_exit_threshold_pct: float = 0.0015,
        slippage_bps: float = 10.0,
        min_tick: float = 0.01,
    ) -> None:
        self._db = db
        self._cache_exit_threshold_pct = max(float(cache_exit_threshold_pct), 0.0)
        self._slippage_bps = max(float(slippage_bps), 0.0)
        self._min_tick = max(float(min_tick), 1e-8)

    def check_exit(self, trade: TradeRecord, current_price: float) -> str | None:
        if trade.stop_loss is None or trade.take_profit is None:
            return None

        if trade.signal == "BUY":
            if current_price <= trade.stop_loss:
                return "sl"
            if current_price >= trade.take_profit:
                return "tp"
        else:
            if current_price >= trade.stop_loss:
                return "sl"
            if current_price <= trade.take_profit:
                return "tp"
        return None

    def can_close_on_source(
        self,
        trade: TradeRecord,
        current_price: float,
        *,
        source: str,
        close_reason: str,
    ) -> bool:
        if source != "cache":
            return True

        trigger_price = trade.stop_loss if close_reason == "sl" else trade.take_profit
        if trigger_price is None:
            return False
        threshold = max(abs(trade.entry_price) * self._cache_exit_threshold_pct, 1e-8)
        return abs(current_price - trigger_price) <= threshold

    def close_trade(
        self,
        trade: TradeRecord,
        exit_price: float,
        *,
        close_reason: str,
        price_source: str,
    ) -> TradeRecord:
        exit_side = "SELL" if trade.signal == "BUY" else "BUY"
        slippage_bps = self._slippage_bps if price_source in {"live", "secondary"} else self._slippage_bps * 0.5
        adjusted_exit_price = apply_slippage(
            exit_price,
            exit_side,
            slippage_bps,
            min_tick=self._min_tick,
        )
        return self._db.close_trade_at_price(
            trade.trade_id,
            exit_price=adjusted_exit_price,
            close_reason=close_reason,
            price_source=price_source,
        )


class TradeLifecycleLoop:
    def __init__(
        self,
        db: SQLiteTradeDatabase,
        monitor_engine: MonitorEngine,
        price_store: MarketPriceStore,
        price_service: PriceService,
        *,
        poll_interval_seconds: float = 5.0,
    ) -> None:
        self._db = db
        self._monitor_engine = monitor_engine
        self._price_store = price_store
        self._price_service = price_service
        self._poll_interval_seconds = max(float(poll_interval_seconds), 1.0)
        self._task: asyncio.Task[None] | None = None
        self._logger = get_logger("trade-lifecycle")

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._run_loop(), name="trade-lifecycle-loop")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None

    async def _run_loop(self) -> None:
        while True:
            await self.run_once()
            await asyncio.sleep(self._poll_interval_seconds)

    async def run_once(self) -> list[TradeRecord]:
        closed_trades: list[TradeRecord] = []
        open_trades = self._db.get_open_trades()
        symbols = [trade.symbol for trade in open_trades]
        manual_prices = self._price_store.consume_prices(symbols)
        prices = dict(manual_prices)

        symbols_to_fetch = [symbol for symbol in {item.upper() for item in symbols} if symbol not in manual_prices]
        if symbols_to_fetch:
            prices.update(await self._price_service.get_prices(symbols_to_fetch))

        for trade in open_trades:
            resolved = prices.get(trade.symbol.upper())
            if resolved is None:
                continue
            current_price, source = resolved
            if current_price is None:
                self._logger.warning("price unavailable symbol=%s source=%s", trade.symbol, source)
                continue
            if source == "mismatch":
                self._logger.warning("price mismatch symbol=%s price=%s", trade.symbol, round(current_price, 8))
                continue
            exit_reason = self._monitor_engine.check_exit(trade, current_price)
            if exit_reason is None:
                continue
            if not self._monitor_engine.can_close_on_source(
                trade,
                current_price,
                source=source,
                close_reason=exit_reason,
            ):
                self._logger.info(
                    "cache price ignored trade_id=%s symbol=%s price=%s reason=%s",
                    trade.trade_id,
                    trade.symbol,
                    round(current_price, 8),
                    exit_reason,
                )
                continue
            closed = self._monitor_engine.close_trade(
                trade,
                current_price,
                close_reason=exit_reason,
                price_source=source,
            )
            self._db.update_trade_from_broker(
                closed.trade_id,
                exchange_status="filled",
                filled_qty=closed.filled_qty or closed.position_size,
                avg_fill_price=closed.exit_price,
                price_source=source,
            )
            closed = self._db.fetch_trade(closed.trade_id)
            self._logger.info(
                "trade closed trade_id=%s symbol=%s source=%s reason=%s pnl=%s",
                closed.trade_id,
                closed.symbol,
                source,
                exit_reason,
                round(closed.pnl, 8),
            )
            closed_trades.append(closed)
        return closed_trades
