from __future__ import annotations

import asyncio
from typing import Any

from db.database import SQLiteTradeDatabase
from models.trade import TradeRecord
from services.broker_adapter import BrokerAdapter
from utils.logger import get_logger


class SyncEngine:
    def __init__(
        self,
        db: SQLiteTradeDatabase,
        broker: BrokerAdapter,
        *,
        attach_orphan_positions: bool = False,
    ) -> None:
        self._db = db
        self._broker = broker
        self._attach_orphan_positions = bool(attach_orphan_positions)
        self._logger = get_logger("broker-sync")

    @staticmethod
    def _normalize_order_id(order_id: str | None) -> str | None:
        if order_id is None:
            return None
        value = str(order_id).strip()
        return value or None

    @staticmethod
    def _normalize_status(payload: dict[str, Any] | None) -> str | None:
        if not payload:
            return None
        status = payload.get("exchange_status") or payload.get("status")
        if status is None:
            return None
        return str(status).strip().upper()

    @staticmethod
    def _safe_float(value: Any, fallback: float | None = None) -> float | None:
        if value is None:
            return fallback
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback

    def _create_orphan_trade(self, symbol: str, position: dict[str, Any]) -> TradeRecord | None:
        side = str(position.get("side") or "BUY").strip().upper()
        entry_price = self._safe_float(position.get("avgPrice"), 0.0) or 0.0
        quantity = self._safe_float(position.get("qty"))
        if entry_price <= 0 or quantity is None or quantity <= 0:
            return None
        trade = TradeRecord(
            strategy="broker_orphan",
            signal="SELL" if side == "SHORT" else side if side in {"BUY", "SELL"} else "BUY",
            symbol=symbol,
            entry_price=entry_price,
            position_size=quantity,
            approved_by_meta=False,
            approved_by_risk=False,
            status="open",
            broker_order_id=self._normalize_order_id(position.get("broker_order_id") or position.get("orderId")),
            exchange_status="open",
            filled_qty=quantity,
            avg_fill_price=entry_price,
        )
        self._db.log_trade(trade)
        return trade

    def run_once(self) -> dict[str, object]:
        broker_positions = {
            symbol.upper(): dict(payload)
            for symbol, payload in self._broker.get_open_positions().items()
        }
        broker_orders = {
            str(order_id): dict(payload)
            for order_id, payload in self._broker.get_open_orders().items()
        }
        db_trades = self._db.get_open_trades()
        db_symbols = {trade.symbol.upper() for trade in db_trades}

        closed_trades: list[TradeRecord] = []
        updated_trades: list[TradeRecord] = []
        unknown_trades: list[TradeRecord] = []
        orphan_trades: list[TradeRecord] = []
        orphan_symbols: list[str] = []

        for trade in db_trades:
            order_id = self._normalize_order_id(trade.broker_order_id)
            broker_order = broker_orders.get(order_id) if order_id else None
            broker_position = broker_positions.get(trade.symbol.upper())

            if broker_order is None and broker_position is None:
                last_order = self._broker.get_order(order_id) if order_id else None
                last_status = self._normalize_status(last_order)
                if last_status in {"FILLED", "CLOSED"}:
                    exit_price = (
                        self._safe_float(last_order.get("avgPrice"), trade.take_profit)
                        if last_order
                        else trade.take_profit
                    )
                    if exit_price is None:
                        exit_price = trade.entry_price
                    closed = self._db.close_trade_at_price(
                        trade.trade_id,
                        exit_price=exit_price,
                        close_reason="broker_fill",
                        price_source="broker",
                        exchange_status="filled",
                        filled_qty=self._safe_float(last_order.get("executedQty"), trade.filled_qty or trade.position_size)
                        if last_order
                        else trade.filled_qty or trade.position_size,
                        avg_fill_price=self._safe_float(last_order.get("avgPrice"), exit_price) if last_order else exit_price,
                    )
                    self._logger.info(
                        "broker sync closed trade_id=%s symbol=%s exit=%s",
                        closed.trade_id,
                        closed.symbol,
                        round(closed.exit_price or 0.0, 8),
                    )
                    closed_trades.append(closed)
                    continue
                updated = self._db.update_trade_from_broker(
                    trade.trade_id,
                    exchange_status="unknown",
                    broker_order_id=order_id,
                )
                unknown_trades.append(updated)
                continue

            order_status = self._normalize_status(broker_order)
            if order_status == "PARTIALLY_FILLED":
                updated = self._db.update_trade_from_broker(
                    trade.trade_id,
                    exchange_status="partial",
                    filled_qty=self._safe_float(broker_order.get("executedQty"), trade.filled_qty or 0.0),
                    avg_fill_price=self._safe_float(broker_order.get("avgPrice"), trade.avg_fill_price or trade.entry_price),
                    broker_order_id=order_id,
                )
                updated_trades.append(updated)
                continue

            if broker_position is not None:
                updated = self._db.update_trade_from_broker(
                    trade.trade_id,
                    exchange_status="open",
                    filled_qty=self._safe_float(
                        broker_position.get("qty"),
                        self._safe_float(broker_order.get("executedQty")) if broker_order else trade.filled_qty or trade.position_size,
                    ),
                    avg_fill_price=self._safe_float(
                        broker_position.get("avgPrice"),
                        self._safe_float(broker_order.get("avgPrice")) if broker_order else trade.avg_fill_price or trade.entry_price,
                    ),
                    broker_order_id=order_id,
                )
                updated_trades.append(updated)
                continue

            updated = self._db.update_trade_from_broker(
                trade.trade_id,
                exchange_status=(order_status or "open").lower(),
                filled_qty=self._safe_float(broker_order.get("executedQty"), trade.filled_qty or trade.position_size) if broker_order else trade.filled_qty,
                avg_fill_price=self._safe_float(broker_order.get("avgPrice"), trade.avg_fill_price or trade.entry_price) if broker_order else trade.avg_fill_price,
                broker_order_id=order_id,
            )
            updated_trades.append(updated)

        for symbol, position in broker_positions.items():
            if symbol in db_symbols:
                continue
            orphan_symbols.append(symbol)
            if not self._attach_orphan_positions:
                continue
            orphan = self._create_orphan_trade(symbol, position)
            if orphan is not None:
                orphan_trades.append(orphan)

        return {
            "closed_trades": closed_trades,
            "updated_trades": updated_trades,
            "unknown_trades": unknown_trades,
            "orphan_trades": orphan_trades,
            "orphan_symbols": orphan_symbols,
            "processed_count": len(db_trades),
        }


class BrokerSyncLoop:
    def __init__(self, sync_engine: SyncEngine, *, poll_interval_seconds: float = 5.0) -> None:
        self._sync_engine = sync_engine
        self._poll_interval_seconds = max(float(poll_interval_seconds), 1.0)
        self._task: asyncio.Task[None] | None = None
        self._logger = get_logger("broker-sync-loop")

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._run_loop(), name="broker-sync-loop")

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
            try:
                self._sync_engine.run_once()
            except Exception as exc:
                self._logger.error("sync error: %s", exc)
            await asyncio.sleep(self._poll_interval_seconds)
