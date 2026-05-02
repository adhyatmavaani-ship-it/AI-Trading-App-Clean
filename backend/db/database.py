from __future__ import annotations

from contextlib import contextmanager
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from models.trade import TradeRecord


class SQLiteTradeDatabase:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _session(self):
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _column_names(self, connection: sqlite3.Connection) -> set[str]:
        rows = connection.execute("PRAGMA table_info(trades)").fetchall()
        return {str(row["name"]) for row in rows}

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if value is None:
            return None
        parsed = datetime.fromisoformat(str(value))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed

    def _initialize(self) -> None:
        with self._session() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS trades (
                    trade_id TEXT PRIMARY KEY,
                    strategy TEXT NOT NULL,
                    signal TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    stop_loss REAL,
                    take_profit REAL,
                    position_size REAL,
                    atr REAL,
                    confidence REAL,
                    exit_price REAL,
                    price_source TEXT,
                    broker_order_id TEXT,
                    exchange_status TEXT,
                    filled_qty REAL,
                    avg_fill_price REAL,
                    pnl REAL NOT NULL DEFAULT 0,
                    approved_by_meta INTEGER NOT NULL DEFAULT 0,
                    approved_by_risk INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    rejection_reason TEXT,
                    close_reason TEXT,
                    timestamp TEXT,
                    created_at TEXT NOT NULL,
                    closed_at TEXT,
                    last_sync_at TEXT
                )
                """
            )
            self._ensure_schema(connection)

    def _ensure_schema(self, connection: sqlite3.Connection) -> None:
        rows = connection.execute("PRAGMA table_info(trades)").fetchall()
        existing_columns = {str(row["name"]) for row in rows}
        required_columns = {
            "trade_id": "TEXT",
            "strategy": "TEXT",
            "signal": "TEXT",
            "symbol": "TEXT",
            "entry_price": "REAL",
            "stop_loss": "REAL",
            "take_profit": "REAL",
            "position_size": "REAL",
            "atr": "REAL",
            "confidence": "REAL",
            "exit_price": "REAL",
            "price_source": "TEXT",
            "broker_order_id": "TEXT",
            "exchange_status": "TEXT",
            "filled_qty": "REAL",
            "avg_fill_price": "REAL",
            "pnl": "REAL NOT NULL DEFAULT 0",
            "approved_by_meta": "INTEGER NOT NULL DEFAULT 0",
            "approved_by_risk": "INTEGER NOT NULL DEFAULT 0",
            "status": "TEXT NOT NULL DEFAULT 'open'",
            "rejection_reason": "TEXT",
            "close_reason": "TEXT",
            "timestamp": "TEXT",
            "created_at": "TEXT",
            "closed_at": "TEXT",
            "last_sync_at": "TEXT",
        }
        for column_name, column_type in required_columns.items():
            if column_name in existing_columns:
                continue
            connection.execute(f"ALTER TABLE trades ADD COLUMN {column_name} {column_type}")

        now = datetime.now(timezone.utc).isoformat()
        connection.execute(
            """
            UPDATE trades
            SET created_at = COALESCE(created_at, closed_at, timestamp, ?)
            WHERE created_at IS NULL
            """,
            (now,),
        )
        connection.execute(
            """
            UPDATE trades
            SET status = CASE
                WHEN status IS NULL OR TRIM(status) = '' THEN
                    CASE
                        WHEN closed_at IS NOT NULL THEN 'closed'
                        ELSE 'open'
                    END
                ELSE status
            END
            """
        )

    def log_trade(self, trade: TradeRecord) -> None:
        with self._session() as connection:
            columns = self._column_names(connection)
            payload: dict[str, object | None] = {
                "trade_id": trade.trade_id,
                "strategy": trade.strategy,
                "signal": trade.signal,
                "symbol": trade.symbol,
                "entry_price": trade.entry_price,
                "stop_loss": trade.stop_loss,
                "take_profit": trade.take_profit,
                "position_size": trade.position_size,
                "atr": trade.atr,
                "confidence": trade.confidence,
                "exit_price": trade.exit_price,
                "price_source": trade.price_source,
                "broker_order_id": trade.broker_order_id,
                "exchange_status": trade.exchange_status,
                "filled_qty": trade.filled_qty,
                "avg_fill_price": trade.avg_fill_price,
                "pnl": trade.pnl,
                "approved_by_meta": int(trade.approved_by_meta),
                "approved_by_risk": int(trade.approved_by_risk),
                "status": trade.status,
                "rejection_reason": trade.rejection_reason,
                "close_reason": trade.close_reason,
                "created_at": trade.created_at.isoformat(),
                "closed_at": trade.closed_at.isoformat() if trade.closed_at else None,
                "last_sync_at": trade.last_sync_at.isoformat() if trade.last_sync_at else None,
            }
            if "result" in columns:
                payload["result"] = self._trade_result(trade.status, trade.pnl)
            if "timestamp" in columns:
                payload["timestamp"] = trade.created_at.isoformat()

            insert_columns = [column for column in payload if column in columns]
            placeholders = ", ".join("?" for _ in insert_columns)
            column_list = ", ".join(insert_columns)
            values = [payload[column] for column in insert_columns]
            connection.execute(
                f"INSERT OR REPLACE INTO trades ({column_list}) VALUES ({placeholders})",
                values,
            )

    def close_trade(
        self,
        trade_id: str,
        *,
        exit_price: float,
        pnl: float,
        close_reason: str | None = None,
        price_source: str | None = None,
        exchange_status: str | None = None,
        filled_qty: float | None = None,
        avg_fill_price: float | None = None,
    ) -> TradeRecord:
        with self._session() as connection:
            row = connection.execute("SELECT * FROM trades WHERE trade_id = ?", (trade_id,)).fetchone()
            if row is None:
                raise KeyError(f"trade not found: {trade_id}")
            if str(row["status"]) == "closed":
                return self._row_to_trade(row)
            closed_at = datetime.now(timezone.utc).isoformat()
            columns = self._column_names(connection)
            assignments = ["exit_price = ?", "pnl = ?", "status = 'closed'", "closed_at = ?"]
            values: list[object] = [exit_price, pnl, closed_at]
            if "close_reason" in columns:
                assignments.append("close_reason = ?")
                values.append(close_reason)
            if "price_source" in columns:
                assignments.append("price_source = ?")
                values.append(price_source)
            if "exchange_status" in columns:
                assignments.append("exchange_status = ?")
                values.append(exchange_status or "filled")
            if "filled_qty" in columns:
                assignments.append("filled_qty = COALESCE(?, filled_qty, position_size)")
                values.append(filled_qty)
            if "avg_fill_price" in columns:
                assignments.append("avg_fill_price = ?")
                values.append(avg_fill_price if avg_fill_price is not None else exit_price)
            if "last_sync_at" in columns:
                assignments.append("last_sync_at = ?")
                values.append(closed_at)
            if "result" in columns:
                assignments.append("result = ?")
                values.append(self._trade_result("closed", pnl))
            values.append(trade_id)
            connection.execute(
                f"UPDATE trades SET {', '.join(assignments)} WHERE trade_id = ?",
                values,
            )
        return self.fetch_trade(trade_id)

    def close_trade_at_price(
        self,
        trade_id: str,
        *,
        exit_price: float,
        close_reason: str | None = None,
        price_source: str | None = None,
        exchange_status: str | None = None,
        filled_qty: float | None = None,
        avg_fill_price: float | None = None,
    ) -> TradeRecord:
        trade = self.fetch_trade(trade_id)
        if trade.status == "closed":
            return trade
        pnl = (exit_price - trade.entry_price) if trade.signal == "BUY" else (trade.entry_price - exit_price)
        return self.close_trade(
            trade_id,
            exit_price=exit_price,
            pnl=pnl,
            close_reason=close_reason,
            price_source=price_source,
            exchange_status=exchange_status,
            filled_qty=filled_qty,
            avg_fill_price=avg_fill_price,
        )

    def update_trade_from_broker(
        self,
        trade_id: str,
        *,
        exchange_status: str | None = None,
        filled_qty: float | None = None,
        avg_fill_price: float | None = None,
        broker_order_id: str | None = None,
        price_source: str | None = None,
    ) -> TradeRecord:
        with self._session() as connection:
            row = connection.execute("SELECT * FROM trades WHERE trade_id = ?", (trade_id,)).fetchone()
            if row is None:
                raise KeyError(f"trade not found: {trade_id}")
            now = datetime.now(timezone.utc).isoformat()
            columns = self._column_names(connection)
            assignments: list[str] = []
            values: list[object] = []
            if "exchange_status" in columns and exchange_status is not None:
                assignments.append("exchange_status = ?")
                values.append(exchange_status)
            if "filled_qty" in columns and filled_qty is not None:
                assignments.append("filled_qty = ?")
                values.append(float(filled_qty))
            if "avg_fill_price" in columns and avg_fill_price is not None:
                assignments.append("avg_fill_price = ?")
                values.append(float(avg_fill_price))
            if "broker_order_id" in columns and broker_order_id is not None:
                assignments.append("broker_order_id = ?")
                values.append(broker_order_id)
            if "price_source" in columns and price_source is not None:
                assignments.append("price_source = ?")
                values.append(price_source)
            if "last_sync_at" in columns:
                assignments.append("last_sync_at = ?")
                values.append(now)
            if not assignments:
                return self._row_to_trade(row)
            values.append(trade_id)
            connection.execute(
                f"UPDATE trades SET {', '.join(assignments)} WHERE trade_id = ?",
                values,
            )
        return self.fetch_trade(trade_id)

    def fetch_trade(self, trade_id: str) -> TradeRecord:
        with self._session() as connection:
            row = connection.execute("SELECT * FROM trades WHERE trade_id = ?", (trade_id,)).fetchone()
        if row is None:
            raise KeyError(f"trade not found: {trade_id}")
        return self._row_to_trade(row)

    def get_recent_trades(self, strategy: str, *, limit: int = 20) -> list[tuple[float, str]]:
        with self._session() as connection:
            rows = connection.execute(
                """
                SELECT pnl, status
                FROM trades
                WHERE strategy = ?
                ORDER BY COALESCE(created_at, timestamp, closed_at) DESC
                LIMIT ?
                """,
                (strategy, limit),
            ).fetchall()
        mapped: list[tuple[float, str]] = []
        for row in rows:
            status = row["status"]
            if status == "closed":
                status = "win" if row["pnl"] > 0 else "loss" if row["pnl"] < 0 else "breakeven"
            mapped.append((float(row["pnl"] or 0.0), str(status)))
        return mapped

    def strategy_names(self) -> list[str]:
        with self._session() as connection:
            rows = connection.execute(
                "SELECT DISTINCT strategy FROM trades ORDER BY strategy ASC"
            ).fetchall()
        return [str(row["strategy"]) for row in rows]

    def daily_pnl(self) -> float:
        day_start = datetime.now(timezone.utc).date().isoformat()
        with self._session() as connection:
            row = connection.execute(
                """
                SELECT COALESCE(SUM(pnl), 0) AS total
                FROM trades
                WHERE substr(COALESCE(closed_at, created_at), 1, 10) = ?
                """,
                (day_start,),
            ).fetchone()
        return float(row["total"] or 0.0)

    def consecutive_losses(self) -> int:
        with self._session() as connection:
            rows = connection.execute(
                """
                SELECT pnl
                FROM trades
                WHERE status = 'closed'
                ORDER BY COALESCE(closed_at, created_at, timestamp) DESC
                """
            ).fetchall()
        streak = 0
        for row in rows:
            pnl = float(row["pnl"] or 0.0)
            if pnl < 0:
                streak += 1
                continue
            break
        return streak

    def summary(self) -> dict[str, int | float]:
        with self._session() as connection:
            row = connection.execute(
                """
                SELECT
                    COUNT(*) AS total_trades,
                    SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) AS open_trades,
                    SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) AS rejected_trades,
                    SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END) AS closed_trades,
                    COALESCE(SUM(pnl), 0) AS total_pnl
                FROM trades
                """
            ).fetchone()
        return {
            "total_trades": int(row["total_trades"] or 0),
            "open_trades": int(row["open_trades"] or 0),
            "rejected_trades": int(row["rejected_trades"] or 0),
            "closed_trades": int(row["closed_trades"] or 0),
            "total_pnl": float(row["total_pnl"] or 0.0),
        }

    def list_trades(self, *, limit: int = 50) -> list[TradeRecord]:
        with self._session() as connection:
            rows = connection.execute(
                "SELECT * FROM trades ORDER BY COALESCE(created_at, timestamp, closed_at) DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_trade(row) for row in rows]

    def get_open_trades(self, *, limit: int = 100) -> list[TradeRecord]:
        with self._session() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM trades
                WHERE status = 'open'
                ORDER BY COALESCE(created_at, timestamp, closed_at) ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_trade(row) for row in rows]

    def _trade_result(self, status: str, pnl: float) -> str:
        if status == "rejected":
            return "rejected"
        if status == "open":
            return "pending"
        if pnl > 0:
            return "win"
        if pnl < 0:
            return "loss"
        return "breakeven"

    def _row_to_trade(self, row: sqlite3.Row) -> TradeRecord:
        return TradeRecord(
            trade_id=str(row["trade_id"]),
            strategy=str(row["strategy"]),
            signal=str(row["signal"]),
            symbol=str(row["symbol"]),
            entry_price=float(row["entry_price"]),
            stop_loss=float(row["stop_loss"]) if row["stop_loss"] is not None else None,
            take_profit=float(row["take_profit"]) if row["take_profit"] is not None else None,
            position_size=float(row["position_size"]) if row["position_size"] is not None else None,
            atr=float(row["atr"]) if row["atr"] is not None else None,
            confidence=float(row["confidence"]) if row["confidence"] is not None else None,
            exit_price=float(row["exit_price"]) if row["exit_price"] is not None else None,
            price_source=str(row["price_source"]) if "price_source" in row.keys() and row["price_source"] is not None else None,
            broker_order_id=str(row["broker_order_id"]) if "broker_order_id" in row.keys() and row["broker_order_id"] is not None else None,
            exchange_status=str(row["exchange_status"]) if "exchange_status" in row.keys() and row["exchange_status"] is not None else None,
            filled_qty=float(row["filled_qty"]) if "filled_qty" in row.keys() and row["filled_qty"] is not None else None,
            avg_fill_price=float(row["avg_fill_price"]) if "avg_fill_price" in row.keys() and row["avg_fill_price"] is not None else None,
            pnl=float(row["pnl"] or 0.0),
            approved_by_meta=bool(row["approved_by_meta"]),
            approved_by_risk=bool(row["approved_by_risk"]),
            status=str(row["status"]),
            rejection_reason=str(row["rejection_reason"]) if row["rejection_reason"] is not None else None,
            close_reason=str(row["close_reason"]) if "close_reason" in row.keys() and row["close_reason"] is not None else None,
            created_at=self._parse_datetime(str(row["created_at"] or row["timestamp"])) or datetime.now(timezone.utc),
            closed_at=self._parse_datetime(str(row["closed_at"])) if row["closed_at"] else None,
            last_sync_at=self._parse_datetime(str(row["last_sync_at"])) if "last_sync_at" in row.keys() and row["last_sync_at"] else None,
        )

    def open_trade_count(self) -> int:
        with self._session() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM trades WHERE status = 'open'"
            ).fetchone()
        return int(row["total"] or 0)

    def latest_executed_trade_time(self) -> datetime | None:
        with self._session() as connection:
            row = connection.execute(
                """
                SELECT COALESCE(created_at, timestamp) AS trade_time
                FROM trades
                WHERE status = 'open' OR status = 'closed'
                ORDER BY COALESCE(created_at, timestamp, closed_at) DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None or row["trade_time"] is None:
            return None
        return self._parse_datetime(str(row["trade_time"]))

    def open_exposure(self) -> float:
        with self._session() as connection:
            row = connection.execute(
                """
                SELECT COALESCE(SUM(ABS(entry_price * COALESCE(filled_qty, position_size))), 0) AS total
                FROM trades
                WHERE status = 'open'
                """
            ).fetchone()
        return float(row["total"] or 0.0)
