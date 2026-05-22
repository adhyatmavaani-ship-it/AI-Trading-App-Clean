from __future__ import annotations

from contextlib import contextmanager
import json
import logging
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar

from models.trade import TradeRecord

logger = logging.getLogger(__name__)


_SCHEMA_TABLES = {
    "trades",
    "strategy_marketplace",
    "pro_scanner_rules",
    "ai_copilot_history",
    "automated_journal_reports",
    "execution_requests",
    "broker_order_acknowledgements",
    "reconciliation_snapshots",
    "execution_audit_events",
}

_T = TypeVar("_T")


class SQLiteTradeDatabase:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        self._metrics = {
            "transactions": 0,
            "lock_contention": 0,
            "slow_transactions": 0,
            "retry_count": 0,
            "last_write_duration_ms": 0.0,
            "last_lock_contention_at": None,
            "last_slow_transaction_at": None,
        }
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=30000")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _transaction(self, operation_name: str, action: Callable[[sqlite3.Connection], _T]) -> _T:
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                with self._session(operation_name=operation_name) as connection:
                    return action(connection)
            except sqlite3.OperationalError as exc:
                if "database is locked" not in str(exc).lower() or attempt >= max_attempts:
                    raise
                backoff_seconds = 0.05 * (2 ** (attempt - 1))
                self._metrics["retry_count"] = int(self._metrics["retry_count"]) + 1
                logger.warning(
                    "sqlite_lock_retry",
                    extra={
                        "event": "sqlite_lock_retry",
                        "context": {
                            "db_path": self._db_path,
                            "operation": operation_name,
                            "attempt": attempt,
                            "backoff_seconds": backoff_seconds,
                        },
                    },
                )
                time.sleep(backoff_seconds)
        raise RuntimeError(f"sqlite transaction retry exhausted for {operation_name}")

    @contextmanager
    def _session(self, *, operation_name: str = "sqlite_transaction"):
        connection = self._connect()
        started = time.perf_counter()
        try:
            yield connection
            connection.commit()
            self._metrics["transactions"] = int(self._metrics["transactions"]) + 1
        except sqlite3.OperationalError as exc:
            connection.rollback()
            if "database is locked" in str(exc).lower():
                self._metrics["lock_contention"] = int(self._metrics["lock_contention"]) + 1
                self._metrics["last_lock_contention_at"] = datetime.now(timezone.utc).isoformat()
                logger.warning(
                    "sqlite_database_lock_contention",
                    extra={
                        "event": "sqlite_database_lock_contention",
                        "context": {"db_path": self._db_path, "operation": operation_name, "error": str(exc)[:200]},
                    },
                )
            raise
        except Exception:
            connection.rollback()
            raise
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            self._metrics["last_write_duration_ms"] = round(elapsed_ms, 4)
            if elapsed_ms > 250:
                self._metrics["slow_transactions"] = int(self._metrics["slow_transactions"]) + 1
                self._metrics["last_slow_transaction_at"] = datetime.now(timezone.utc).isoformat()
                logger.warning(
                    "sqlite_slow_transaction",
                    extra={
                        "event": "sqlite_slow_transaction",
                        "context": {
                            "db_path": self._db_path,
                            "operation": operation_name,
                            "elapsed_ms": round(elapsed_ms, 4),
                        },
                    },
                )
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
            self._initialize_pro_feature_tables(connection)
            self._initialize_execution_feature_tables(connection)
            self._ensure_schema(connection)
            self._ensure_pro_feature_schema(connection)

    def _initialize_pro_feature_tables(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS strategy_marketplace (
                id TEXT PRIMARY KEY,
                creator_id TEXT NOT NULL,
                strategy_name TEXT NOT NULL,
                total_trades INTEGER DEFAULT 0,
                win_rate REAL DEFAULT 0.0,
                profit_factor REAL DEFAULT 0.0,
                max_drawdown REAL DEFAULT 0.0,
                is_verified INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS pro_scanner_rules (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                rule_name TEXT NOT NULL,
                rsi_threshold REAL,
                volume_multiplier REAL,
                macd_criteria TEXT,
                webhook_url TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_copilot_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                role TEXT CHECK(role IN ('user', 'assistant')),
                message TEXT NOT NULL,
                grounded_ticker TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS automated_journal_reports (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                trade_id TEXT NOT NULL UNIQUE,
                ticker TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                psychology_tags TEXT,
                svg_snapshot_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_strategy_marketplace_creator ON strategy_marketplace (creator_id, created_at)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_pro_scanner_rules_user ON pro_scanner_rules (user_id, is_active, created_at)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_ai_copilot_history_session ON ai_copilot_history (user_id, session_id, created_at)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_automated_journal_user ON automated_journal_reports (user_id, created_at)"
        )

    def _initialize_execution_feature_tables(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS execution_requests (
                execution_request_id TEXT PRIMARY KEY,
                idempotency_key_hash TEXT NOT NULL UNIQUE,
                user_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                status TEXT NOT NULL,
                execution_attempt INTEGER NOT NULL DEFAULT 1,
                execution_origin TEXT NOT NULL DEFAULT 'api',
                signal_id TEXT,
                trade_id TEXT,
                request_json TEXT NOT NULL DEFAULT '{}',
                response_json TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                requested_at TEXT,
                validated_at TEXT,
                submitted_at TEXT,
                acknowledged_at TEXT,
                filled_at TEXT,
                failed_at TEXT,
                cancelled_at TEXT,
                recovery_reason TEXT,
                recovery_attempts INTEGER NOT NULL DEFAULT 0,
                recovery_last_checked_at TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS broker_order_acknowledgements (
                client_order_id TEXT PRIMARY KEY,
                execution_request_id TEXT,
                broker_order_id TEXT,
                exchange TEXT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                status TEXT NOT NULL,
                ack_json TEXT NOT NULL DEFAULT '{}',
                duplicate_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS reconciliation_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                checked_at TEXT NOT NULL,
                local_active INTEGER NOT NULL DEFAULT 0,
                broker_active INTEGER NOT NULL DEFAULT 0,
                mismatch_count INTEGER NOT NULL DEFAULT 0,
                duplicate_ack_count INTEGER NOT NULL DEFAULT 0,
                payload_json TEXT NOT NULL DEFAULT '{}'
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS execution_audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                execution_request_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_execution_requests_status ON execution_requests (status, updated_at)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_execution_requests_trade ON execution_requests (trade_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_broker_ack_execution ON broker_order_acknowledgements (execution_request_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_broker_ack_broker_order ON broker_order_acknowledgements (exchange, broker_order_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_reconciliation_snapshots_checked ON reconciliation_snapshots (checked_at)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_execution_audit_request ON execution_audit_events (execution_request_id, created_at)"
        )

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

    def _ensure_pro_feature_schema(self, connection: sqlite3.Connection) -> None:
        self._ensure_columns(
            connection,
            "strategy_marketplace",
            {
                "style": "TEXT DEFAULT 'trend_following'",
                "description": "TEXT",
                "markets_json": "TEXT DEFAULT '[]'",
                "evidence_type": "TEXT DEFAULT 'paper_ledger'",
            },
        )
        self._ensure_columns(
            connection,
            "pro_scanner_rules",
            {
                "timeframe": "TEXT DEFAULT '1h'",
                "symbols_json": "TEXT DEFAULT '[]'",
                "criteria_json": "TEXT DEFAULT '[]'",
                "last_match_count": "INTEGER DEFAULT 0",
                "last_triggered_at": "TEXT",
            },
        )
        self._ensure_columns(
            connection,
            "ai_copilot_history",
            {
                "metadata_json": "TEXT DEFAULT '{}'",
            },
        )
        self._ensure_columns(
            connection,
            "automated_journal_reports",
            {
                "pnl": "REAL DEFAULT 0.0",
                "analysis": "TEXT",
                "behavioral_summary_json": "TEXT DEFAULT '{}'",
            },
        )
        self._ensure_columns(
            connection,
            "execution_requests",
            {
                "recovery_reason": "TEXT",
                "recovery_attempts": "INTEGER NOT NULL DEFAULT 0",
                "recovery_last_checked_at": "TEXT",
            },
        )

    def _ensure_columns(
        self,
        connection: sqlite3.Connection,
        table_name: str,
        required_columns: dict[str, str],
    ) -> None:
        if table_name not in _SCHEMA_TABLES:
            raise ValueError(f"unsupported schema table: {table_name}")
        rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        existing_columns = {str(row["name"]) for row in rows}
        for column_name, column_type in required_columns.items():
            if column_name in existing_columns:
                continue
            connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")

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

    def claim_execution_request(
        self,
        *,
        execution_request_id: str,
        idempotency_key_hash: str,
        request_payload: dict[str, Any],
        execution_origin: str,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        user_id = str(request_payload.get("user_id", ""))
        symbol = str(request_payload.get("symbol", "")).upper()
        side = str(request_payload.get("side", "")).upper()
        signal_id = str(request_payload.get("signal_id") or execution_request_id)

        def action(connection: sqlite3.Connection) -> dict[str, Any]:
            row = connection.execute(
                """
                SELECT *
                FROM execution_requests
                WHERE execution_request_id = ? OR idempotency_key_hash = ?
                LIMIT 1
                """,
                (execution_request_id, idempotency_key_hash),
            ).fetchone()
            if row is None:
                connection.execute(
                    """
                    INSERT INTO execution_requests (
                        execution_request_id,
                        idempotency_key_hash,
                        user_id,
                        symbol,
                        side,
                        status,
                        execution_attempt,
                        execution_origin,
                        signal_id,
                        request_json,
                        created_at,
                        updated_at,
                        requested_at
                    ) VALUES (?, ?, ?, ?, ?, 'REQUESTED', 1, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        execution_request_id,
                        idempotency_key_hash,
                        user_id,
                        symbol,
                        side,
                        execution_origin,
                        signal_id,
                        json.dumps(request_payload, default=str),
                        now,
                        now,
                        now,
                    ),
                )
                row = connection.execute(
                    "SELECT * FROM execution_requests WHERE execution_request_id = ?",
                    (execution_request_id,),
                ).fetchone()
                return {**self._row_to_dict(row), "claimed": True}

            connection.execute(
                """
                UPDATE execution_requests
                SET execution_attempt = execution_attempt + 1,
                    updated_at = ?,
                    execution_origin = COALESCE(NULLIF(?, ''), execution_origin)
                WHERE execution_request_id = ?
                """,
                (now, execution_origin, str(row["execution_request_id"])),
            )
            updated = connection.execute(
                "SELECT * FROM execution_requests WHERE execution_request_id = ?",
                (str(row["execution_request_id"]),),
            ).fetchone()
            return {**self._row_to_dict(updated), "claimed": False}

        return self._transaction("claim_execution_request", action)

    def execution_request_by_id(self, execution_request_id: str) -> dict[str, Any] | None:
        with self._session(operation_name="execution_request_by_id") as connection:
            row = connection.execute(
                "SELECT * FROM execution_requests WHERE execution_request_id = ?",
                (execution_request_id,),
            ).fetchone()
        return self._row_to_dict(row) if row is not None else None

    def update_execution_request_status(
        self,
        execution_request_id: str,
        *,
        status: str,
        trade_id: str | None = None,
        response: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        normalized_status = str(status or "").upper()
        status_column = {
            "REQUESTED": "requested_at",
            "VALIDATED": "validated_at",
            "SUBMITTED": "submitted_at",
            "ACKNOWLEDGED": "acknowledged_at",
            "FILLED": "filled_at",
            "FAILED": "failed_at",
            "CANCELLED": "cancelled_at",
        }.get(normalized_status)
        now = datetime.now(timezone.utc).isoformat()
        assignments = ["status = ?", "updated_at = ?"]
        values: list[Any] = [normalized_status, now]
        if status_column is not None:
            assignments.append(f"{status_column} = COALESCE({status_column}, ?)")
            values.append(now)
        if trade_id is not None:
            assignments.append("trade_id = ?")
            values.append(trade_id)
        if response is not None:
            assignments.append("response_json = ?")
            values.append(json.dumps(response, default=str))
        if error is not None:
            assignments.append("error = ?")
            values.append(str(error)[:500])
        values.append(execution_request_id)
        def action(connection: sqlite3.Connection) -> None:
            connection.execute(
                f"UPDATE execution_requests SET {', '.join(assignments)} WHERE execution_request_id = ?",
                values,
            )

        self._transaction("update_execution_request_status", action)

    def mark_execution_recovery_checked(
        self,
        execution_request_id: str,
        *,
        recovery_reason: str,
    ) -> dict[str, Any] | None:
        now = datetime.now(timezone.utc).isoformat()

        def action(connection: sqlite3.Connection) -> dict[str, Any] | None:
            connection.execute(
                """
                UPDATE execution_requests
                SET recovery_reason = ?,
                    recovery_attempts = recovery_attempts + 1,
                    recovery_last_checked_at = ?,
                    updated_at = ?
                WHERE execution_request_id = ?
                """,
                (str(recovery_reason)[:300], now, now, execution_request_id),
            )
            row = connection.execute(
                "SELECT * FROM execution_requests WHERE execution_request_id = ?",
                (execution_request_id,),
            ).fetchone()
            return self._row_to_dict(row) if row is not None else None

        return self._transaction("mark_execution_recovery_checked", action)

    def orphan_execution_requests(self, *, stale_after_seconds: float | None = None) -> list[dict[str, Any]]:
        with self._session(operation_name="orphan_execution_requests") as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM execution_requests
                WHERE status IN ('REQUESTED', 'VALIDATED', 'SUBMITTED', 'ACKNOWLEDGED', 'UNKNOWN_AFTER_ERROR')
                ORDER BY updated_at ASC
                """
            ).fetchall()
        orphans = [self._row_to_dict(row) for row in rows]
        if stale_after_seconds is None:
            return orphans
        now = datetime.now(timezone.utc)
        stale: list[dict[str, Any]] = []
        for row in orphans:
            updated_at = self._parse_datetime(str(row.get("updated_at"))) if row.get("updated_at") else None
            age_seconds = None if updated_at is None else (now - updated_at.astimezone(timezone.utc)).total_seconds()
            row["age_seconds"] = round(age_seconds, 3) if age_seconds is not None else None
            if age_seconds is None or age_seconds >= float(stale_after_seconds):
                stale.append(row)
        return stale

    def broker_acknowledgement_by_client_order_id(self, client_order_id: str) -> dict[str, Any] | None:
        with self._session(operation_name="broker_acknowledgement_by_client_order_id") as connection:
            row = connection.execute(
                "SELECT * FROM broker_order_acknowledgements WHERE client_order_id = ?",
                (client_order_id,),
            ).fetchone()
        return self._broker_ack_row(row) if row is not None else None

    def broker_acknowledgements_for_execution(self, execution_request_id: str) -> list[dict[str, Any]]:
        with self._session(operation_name="broker_acknowledgements_for_execution") as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM broker_order_acknowledgements
                WHERE execution_request_id = ?
                ORDER BY created_at ASC
                """,
                (execution_request_id,),
            ).fetchall()
        return [self._broker_ack_row(row) for row in rows]

    def record_broker_acknowledgement(
        self,
        *,
        client_order_id: str,
        execution_request_id: str | None,
        broker_order_id: str | None,
        exchange: str | None,
        symbol: str,
        side: str,
        status: str,
        ack_payload: dict[str, Any],
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()

        def action(connection: sqlite3.Connection) -> dict[str, Any]:
            existing = connection.execute(
                "SELECT * FROM broker_order_acknowledgements WHERE client_order_id = ?",
                (client_order_id,),
            ).fetchone()
            if existing is not None:
                connection.execute(
                    """
                    UPDATE broker_order_acknowledgements
                    SET duplicate_count = duplicate_count + 1,
                        updated_at = ?
                    WHERE client_order_id = ?
                    """,
                    (now, client_order_id),
                )
                updated = connection.execute(
                    "SELECT * FROM broker_order_acknowledgements WHERE client_order_id = ?",
                    (client_order_id,),
                ).fetchone()
                return {**self._broker_ack_row(updated), "duplicate": True}
            connection.execute(
                """
                INSERT INTO broker_order_acknowledgements (
                    client_order_id,
                    execution_request_id,
                    broker_order_id,
                    exchange,
                    symbol,
                    side,
                    status,
                    ack_json,
                    duplicate_count,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (
                    client_order_id,
                    execution_request_id,
                    broker_order_id,
                    exchange,
                    symbol.upper(),
                    side.upper(),
                    status,
                    json.dumps(ack_payload, default=str),
                    now,
                    now,
                ),
            )
            row = connection.execute(
                "SELECT * FROM broker_order_acknowledgements WHERE client_order_id = ?",
                (client_order_id,),
            ).fetchone()
            return {**self._broker_ack_row(row), "duplicate": False}

        return self._transaction("record_broker_acknowledgement", action)

    def save_reconciliation_snapshot(self, payload: dict[str, Any]) -> None:
        checked_at = str(payload.get("checked_at") or datetime.now(timezone.utc).isoformat())
        def action(connection: sqlite3.Connection) -> None:
            connection.execute(
                """
                INSERT INTO reconciliation_snapshots (
                    checked_at,
                    local_active,
                    broker_active,
                    mismatch_count,
                    duplicate_ack_count,
                    payload_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    checked_at,
                    int(payload.get("local_active", 0) or 0),
                    int(payload.get("broker_active", 0) or 0),
                    int(payload.get("mismatch_count", 0) or 0),
                    int(payload.get("duplicate_ack_count", 0) or 0),
                    json.dumps(payload, default=str),
                ),
            )

        self._transaction("save_reconciliation_snapshot", action)

    def latest_reconciliation_snapshot(self) -> dict[str, Any] | None:
        with self._session(operation_name="latest_reconciliation_snapshot") as connection:
            row = connection.execute(
                """
                SELECT *
                FROM reconciliation_snapshots
                ORDER BY checked_at DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return None
        payload = self._json_dict(row["payload_json"])
        payload.setdefault("checked_at", str(row["checked_at"]))
        return payload

    def append_execution_audit_event(
        self,
        execution_request_id: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        created_at = datetime.now(timezone.utc).isoformat()

        def action(connection: sqlite3.Connection) -> dict[str, Any]:
            cursor = connection.execute(
                """
                INSERT INTO execution_audit_events (
                    execution_request_id,
                    event_type,
                    event_payload_json,
                    created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    execution_request_id,
                    str(event_type),
                    json.dumps(payload or {}, default=str),
                    created_at,
                ),
            )
            return {
                "id": int(cursor.lastrowid),
                "execution_request_id": execution_request_id,
                "event_type": str(event_type),
                "payload": payload or {},
                "created_at": created_at,
            }

        return self._transaction("append_execution_audit_event", action)

    def execution_audit_events(self, execution_request_id: str) -> list[dict[str, Any]]:
        with self._session(operation_name="execution_audit_events") as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM execution_audit_events
                WHERE execution_request_id = ?
                ORDER BY id ASC
                """,
                (execution_request_id,),
            ).fetchall()
        events: list[dict[str, Any]] = []
        for row in rows:
            payload = self._row_to_dict(row)
            payload["payload"] = self._json_dict(payload.get("event_payload_json"))
            events.append(payload)
        return events

    def execution_recovery_summary(self) -> dict[str, Any]:
        with self._session(operation_name="execution_recovery_summary") as connection:
            rows = connection.execute(
                """
                SELECT status, COUNT(*) AS count
                FROM execution_requests
                GROUP BY status
                """
            ).fetchall()
            orphan_count = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM execution_requests
                WHERE status IN ('REQUESTED', 'VALIDATED', 'SUBMITTED', 'ACKNOWLEDGED', 'UNKNOWN_AFTER_ERROR')
                """
            ).fetchone()
        return {
            "status_counts": {str(row["status"]): int(row["count"] or 0) for row in rows},
            "orphan_execution_count": int(orphan_count["count"] or 0),
        }

    def db_write_pressure(self) -> dict[str, Any]:
        return dict(self._metrics)

    def save_strategy_marketplace_record(self, record: dict[str, Any]) -> None:
        metrics = dict(record.get("metrics") or {})
        with self._session() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO strategy_marketplace (
                    id,
                    creator_id,
                    strategy_name,
                    total_trades,
                    win_rate,
                    profit_factor,
                    max_drawdown,
                    is_verified,
                    created_at,
                    style,
                    description,
                    markets_json,
                    evidence_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(record.get("strategy_id", record.get("id", ""))),
                    str(record.get("publisher_user_id", record.get("creator_id", ""))),
                    str(record.get("name", record.get("strategy_name", ""))),
                    int(metrics.get("trade_count", record.get("total_trades", 0)) or 0),
                    float(metrics.get("win_rate", record.get("win_rate", 0.0)) or 0.0),
                    float(metrics.get("profit_factor", record.get("profit_factor", 0.0)) or 0.0),
                    float(metrics.get("max_drawdown", record.get("max_drawdown", 0.0)) or 0.0),
                    1 if bool(record.get("verified", record.get("is_verified", True))) else 0,
                    str(record.get("published_at", record.get("created_at", datetime.now(timezone.utc).isoformat()))),
                    str(record.get("style", "trend_following")),
                    str(record.get("description", "")),
                    json.dumps(list(record.get("markets") or [])),
                    str(record.get("evidence_type", "paper_ledger")),
                ),
            )

    def list_strategy_marketplace_records(self) -> list[dict[str, Any]]:
        with self._session() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM strategy_marketplace
                ORDER BY created_at DESC
                """
            ).fetchall()
        records: list[dict[str, Any]] = []
        for row in rows:
            records.append(
                {
                    "strategy_id": str(row["id"]),
                    "publisher_user_id": str(row["creator_id"]),
                    "name": str(row["strategy_name"]),
                    "description": str(row["description"] or ""),
                    "style": str(row["style"] or "trend_following"),
                    "markets": self._json_list(row["markets_json"]),
                    "evidence_type": str(row["evidence_type"] or "paper_ledger"),
                    "metrics": {
                        "trade_count": int(row["total_trades"] or 0),
                        "win_rate": float(row["win_rate"] or 0.0),
                        "profit_factor": float(row["profit_factor"] or 0.0),
                        "max_drawdown": float(row["max_drawdown"] or 0.0),
                    },
                    "verified": bool(row["is_verified"]),
                    "verification_note": "Ledger-backed performance record accepted; screenshots are not used as proof.",
                    "published_at": str(row["created_at"]),
                }
            )
        return records

    def save_pro_scanner_rule(
        self,
        *,
        rule_id: str,
        user_id: str,
        rule_name: str,
        timeframe: str,
        symbols: list[str],
        criteria: list[dict[str, Any]],
        webhook_url: str | None,
        match_count: int,
    ) -> None:
        rsi_threshold = self._criterion_value(criteria, "rsi")
        volume_multiplier = self._criterion_value(criteria, "volume_ratio")
        macd_criteria = self._criterion_text(criteria, "macd_crossover")
        triggered_at = datetime.now(timezone.utc).isoformat() if match_count > 0 else None
        with self._session() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO pro_scanner_rules (
                    id,
                    user_id,
                    rule_name,
                    rsi_threshold,
                    volume_multiplier,
                    macd_criteria,
                    webhook_url,
                    is_active,
                    created_at,
                    timeframe,
                    symbols_json,
                    criteria_json,
                    last_match_count,
                    last_triggered_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, COALESCE((SELECT created_at FROM pro_scanner_rules WHERE id = ?), ?), ?, ?, ?, ?, ?)
                """,
                (
                    rule_id,
                    user_id,
                    rule_name,
                    rsi_threshold,
                    volume_multiplier,
                    macd_criteria,
                    webhook_url,
                    rule_id,
                    datetime.now(timezone.utc).isoformat(),
                    timeframe,
                    json.dumps(symbols),
                    json.dumps(criteria),
                    int(match_count),
                    triggered_at,
                ),
            )

    def list_pro_scanner_rules(self, *, user_id: str) -> list[dict[str, Any]]:
        with self._session() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM pro_scanner_rules
                WHERE user_id = ?
                ORDER BY created_at DESC
                """,
                (user_id,),
            ).fetchall()
        return [
            {
                "id": str(row["id"]),
                "user_id": str(row["user_id"]),
                "rule_name": str(row["rule_name"]),
                "rsi_threshold": float(row["rsi_threshold"]) if row["rsi_threshold"] is not None else None,
                "volume_multiplier": float(row["volume_multiplier"]) if row["volume_multiplier"] is not None else None,
                "macd_criteria": str(row["macd_criteria"] or ""),
                "webhook_url": str(row["webhook_url"] or ""),
                "is_active": bool(row["is_active"]),
                "timeframe": str(row["timeframe"] or "1h"),
                "symbols": self._json_list(row["symbols_json"]),
                "criteria": self._json_list(row["criteria_json"]),
                "last_match_count": int(row["last_match_count"] or 0),
                "last_triggered_at": row["last_triggered_at"],
                "created_at": str(row["created_at"]),
            }
            for row in rows
        ]

    def append_ai_copilot_history(
        self,
        *,
        user_id: str,
        session_id: str,
        role: str,
        message: str,
        grounded_ticker: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        with self._session() as connection:
            connection.execute(
                """
                INSERT INTO ai_copilot_history (
                    user_id,
                    session_id,
                    role,
                    message,
                    grounded_ticker,
                    metadata_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    session_id,
                    role,
                    message,
                    grounded_ticker,
                    json.dumps(metadata or {}),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def list_ai_copilot_history(self, *, user_id: str, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with self._session() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM ai_copilot_history
                WHERE user_id = ? AND session_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (user_id, session_id, int(limit)),
            ).fetchall()
        return [
            {
                "id": int(row["id"]),
                "user_id": str(row["user_id"]),
                "session_id": str(row["session_id"]),
                "role": str(row["role"]),
                "message": str(row["message"]),
                "grounded_ticker": str(row["grounded_ticker"] or ""),
                "metadata": self._json_dict(row["metadata_json"]),
                "created_at": str(row["created_at"]),
            }
            for row in rows
        ]

    def save_automated_journal_report(self, report: dict[str, Any], *, trade: dict[str, Any]) -> None:
        trade_id = str(trade.get("trade_id") or f"{report.get('symbol')}:{report.get('generated_at')}")
        snapshot = dict(report.get("snapshot_image") or {})
        with self._session() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO automated_journal_reports (
                    id,
                    user_id,
                    trade_id,
                    ticker,
                    entry_price,
                    exit_price,
                    psychology_tags,
                    svg_snapshot_url,
                    created_at,
                    pnl,
                    analysis,
                    behavioral_summary_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(report.get("report_id") or f"journal_{trade_id}"),
                    str(report.get("user_id", "")),
                    trade_id,
                    str(report.get("symbol", trade.get("symbol", ""))).upper(),
                    float(trade.get("entry_price", trade.get("entry", 0.0)) or 0.0),
                    float(trade.get("exit_price", trade.get("exit", 0.0)) or 0.0),
                    json.dumps(list(report.get("psychology_tags") or [])),
                    str(snapshot.get("data_url", "")),
                    str(report.get("generated_at", datetime.now(timezone.utc).isoformat())),
                    float(report.get("pnl", 0.0) or 0.0),
                    str(report.get("analysis", "")),
                    json.dumps(dict(report.get("behavioral_summary") or {})),
                ),
            )

    def list_automated_journal_reports(self, *, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with self._session() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM automated_journal_reports
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (user_id, int(limit)),
            ).fetchall()
        return [
            {
                "id": str(row["id"]),
                "user_id": str(row["user_id"]),
                "trade_id": str(row["trade_id"]),
                "symbol": str(row["ticker"]),
                "entry_price": float(row["entry_price"] or 0.0),
                "exit_price": float(row["exit_price"] or 0.0),
                "psychology_tags": self._json_list(row["psychology_tags"]),
                "snapshot_image": {"mime_type": "image/svg+xml", "data_url": str(row["svg_snapshot_url"] or "")},
                "pnl": float(row["pnl"] or 0.0),
                "analysis": str(row["analysis"] or ""),
                "behavioral_summary": self._json_dict(row["behavioral_summary_json"]),
                "generated_at": str(row["created_at"]),
            }
            for row in rows
        ]

    def pro_feature_table_names(self) -> set[str]:
        with self._session() as connection:
            rows = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            ).fetchall()
        return {str(row["name"]) for row in rows}

    def _json_list(self, value: object) -> list[Any]:
        try:
            parsed = json.loads(str(value or "[]"))
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []

    def _json_dict(self, value: object) -> dict[str, Any]:
        try:
            parsed = json.loads(str(value or "{}"))
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _row_to_dict(self, row: sqlite3.Row | None) -> dict[str, Any]:
        if row is None:
            return {}
        return {str(key): row[key] for key in row.keys()}

    def _broker_ack_row(self, row: sqlite3.Row | None) -> dict[str, Any]:
        payload = self._row_to_dict(row)
        if not payload:
            return {}
        payload["ack"] = self._json_dict(payload.get("ack_json"))
        return payload

    def _criterion_value(self, criteria: list[dict[str, Any]], field: str) -> float | None:
        for item in criteria:
            if str(item.get("field", "")).lower() != field:
                continue
            try:
                return float(item.get("value"))
            except (TypeError, ValueError):
                return None
        return None

    def _criterion_text(self, criteria: list[dict[str, Any]], field: str) -> str | None:
        for item in criteria:
            if str(item.get("field", "")).lower() == field:
                return str(item.get("value", ""))
        return None
