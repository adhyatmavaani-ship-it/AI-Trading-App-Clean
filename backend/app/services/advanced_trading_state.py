from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from app.core.config import get_settings
from app.schemas.advanced_trading import (
    AiStrategyContextRequest,
    ChartOrderSyncRequest,
    new_chart_order_id,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


class AdvancedTradingStateRepository:
    """Durable advisory state for UI chart orders and AI context.

    This service deliberately does not call execution, broker, or risk services.
    It stores explainability and chart line state so the frontend can sync fast
    without creating an execution path.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path, timeout=15.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=15000")
        return connection

    @contextmanager
    def _session(self):
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._session() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS user_api_keys (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    label TEXT NOT NULL,
                    key_hash TEXT NOT NULL,
                    encrypted_key TEXT NOT NULL,
                    encryption_iv TEXT NOT NULL,
                    encryption_tag TEXT NOT NULL,
                    key_preview TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(user_id, provider, key_hash)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_strategies (
                    ai_strategy_id TEXT PRIMARY KEY,
                    slug TEXT NOT NULL,
                    version TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    model_family TEXT NOT NULL,
                    metrics_json TEXT NOT NULL DEFAULT '{}',
                    risk_context_json TEXT NOT NULL DEFAULT '{}',
                    signal_context_json TEXT NOT NULL DEFAULT '{}',
                    last_signal_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(slug, version)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS chart_orders (
                    chart_order_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    ai_strategy_id TEXT,
                    workspace_mode TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    exchange TEXT NOT NULL,
                    side TEXT NOT NULL,
                    order_type TEXT NOT NULL,
                    limit_price REAL,
                    stop_loss REAL,
                    take_profit REAL,
                    quantity REAL,
                    is_ai_trailing INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    client_revision INTEGER NOT NULL DEFAULT 1,
                    chart_context_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    last_updated TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS chart_order_events (
                    event_id TEXT PRIMARY KEY,
                    chart_order_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    claimed_at TEXT,
                    completed_at TEXT,
                    error TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS chart_order_testnet_actions (
                    action_id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL UNIQUE,
                    chart_order_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    price REAL,
                    quantity REAL,
                    is_ai_trailing INTEGER NOT NULL DEFAULT 0,
                    credential_provider TEXT,
                    credential_key_preview TEXT,
                    action_payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_user_api_keys_user ON user_api_keys (user_id, provider)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_ai_strategies_slug ON ai_strategies (slug, version)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_chart_orders_user ON chart_orders (user_id, last_updated)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_chart_orders_symbol ON chart_orders (symbol, status, last_updated)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_chart_orders_strategy ON chart_orders (ai_strategy_id, last_updated)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_chart_order_events_pending ON chart_order_events (status, created_at)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_chart_order_events_order ON chart_order_events (chart_order_id, created_at)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_chart_order_actions_user ON chart_order_testnet_actions (user_id, created_at)")

    def store_encrypted_api_key(
        self,
        *,
        user_id: str,
        provider: str,
        label: str,
        key_hash: str,
        encrypted_key: str,
        encryption_iv: str,
        encryption_tag: str,
        key_preview: str,
    ) -> dict[str, Any]:
        now = _now_iso()
        key_id = str(uuid5(NAMESPACE_URL, f"quentrader:user-api-key:{user_id}:{provider}:{key_hash}"))
        with self._session() as connection:
            connection.execute(
                """
                INSERT INTO user_api_keys (
                    id, user_id, provider, label, key_hash, encrypted_key,
                    encryption_iv, encryption_tag, key_preview, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, provider, key_hash) DO UPDATE SET
                    label = excluded.label,
                    encrypted_key = excluded.encrypted_key,
                    encryption_iv = excluded.encryption_iv,
                    encryption_tag = excluded.encryption_tag,
                    key_preview = excluded.key_preview,
                    is_active = 1,
                    updated_at = excluded.updated_at
                """,
                (
                    key_id,
                    user_id,
                    provider,
                    label,
                    key_hash,
                    encrypted_key,
                    encryption_iv,
                    encryption_tag,
                    key_preview,
                    now,
                    now,
                ),
            )
            row = connection.execute("SELECT * FROM user_api_keys WHERE id = ?", (key_id,)).fetchone()
        return self._row_to_api_key(row)

    def upsert_ai_strategy_context(self, payload: AiStrategyContextRequest) -> dict[str, Any]:
        now = _now_iso()
        strategy_id = str(uuid5(NAMESPACE_URL, f"quentrader:ai-strategy:{payload.slug}:{payload.version}"))
        with self._session() as connection:
            connection.execute(
                """
                INSERT INTO ai_strategies (
                    ai_strategy_id, slug, version, display_name, model_family,
                    metrics_json, risk_context_json, signal_context_json,
                    last_signal_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(slug, version) DO UPDATE SET
                    display_name = excluded.display_name,
                    model_family = excluded.model_family,
                    metrics_json = excluded.metrics_json,
                    risk_context_json = excluded.risk_context_json,
                    signal_context_json = excluded.signal_context_json,
                    last_signal_at = excluded.last_signal_at,
                    updated_at = excluded.updated_at
                """,
                (
                    strategy_id,
                    payload.slug,
                    payload.version,
                    payload.display_name,
                    payload.model_family,
                    json.dumps(payload.metrics, sort_keys=True, default=str),
                    json.dumps(payload.risk_context, sort_keys=True, default=str),
                    json.dumps(payload.signal_context, sort_keys=True, default=str),
                    now,
                    now,
                    now,
                ),
            )
            row = connection.execute("SELECT * FROM ai_strategies WHERE ai_strategy_id = ?", (strategy_id,)).fetchone()
        return self._row_to_strategy(row)

    def get_ai_strategy_context(self, ai_strategy_id: str) -> dict[str, Any] | None:
        with self._session() as connection:
            row = connection.execute(
                "SELECT * FROM ai_strategies WHERE ai_strategy_id = ?",
                (ai_strategy_id,),
            ).fetchone()
        return self._row_to_strategy(row) if row is not None else None

    def latest_ai_strategy_contexts(self, *, limit: int = 25) -> list[dict[str, Any]]:
        normalized_limit = max(1, min(int(limit), 100))
        with self._session() as connection:
            rows = connection.execute(
                """
                SELECT * FROM ai_strategies
                ORDER BY COALESCE(last_signal_at, updated_at, created_at) DESC
                LIMIT ?
                """,
                (normalized_limit,),
            ).fetchall()
        return [self._row_to_strategy(row) for row in rows]

    def sync_chart_order(self, *, user_id: str, payload: ChartOrderSyncRequest) -> dict[str, Any]:
        now = _now_iso()
        chart_order_id = payload.chart_order_id or new_chart_order_id()
        with self._session() as connection:
            existing = connection.execute(
                "SELECT user_id, created_at FROM chart_orders WHERE chart_order_id = ?",
                (chart_order_id,),
            ).fetchone()
            if existing is not None and str(existing["user_id"]) != user_id:
                raise PermissionError("chart order belongs to another user")
            created_at = str(existing["created_at"]) if existing is not None else now
            connection.execute(
                """
                INSERT INTO chart_orders (
                    chart_order_id, user_id, ai_strategy_id, workspace_mode, symbol, exchange,
                    side, order_type, limit_price, stop_loss, take_profit, quantity,
                    is_ai_trailing, status, client_revision, chart_context_json,
                    created_at, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chart_order_id) DO UPDATE SET
                    ai_strategy_id = excluded.ai_strategy_id,
                    workspace_mode = excluded.workspace_mode,
                    symbol = excluded.symbol,
                    exchange = excluded.exchange,
                    side = excluded.side,
                    order_type = excluded.order_type,
                    limit_price = excluded.limit_price,
                    stop_loss = excluded.stop_loss,
                    take_profit = excluded.take_profit,
                    quantity = excluded.quantity,
                    is_ai_trailing = excluded.is_ai_trailing,
                    status = excluded.status,
                    client_revision = excluded.client_revision,
                    chart_context_json = excluded.chart_context_json,
                    last_updated = excluded.last_updated
                """,
                (
                    chart_order_id,
                    user_id,
                    payload.ai_strategy_id,
                    payload.workspace_mode,
                    payload.symbol,
                    payload.exchange,
                    payload.side,
                    payload.order_type,
                    payload.limit_price,
                    payload.stop_loss,
                    payload.take_profit,
                    payload.quantity,
                    int(payload.is_ai_trailing),
                    payload.status,
                    payload.client_revision,
                    json.dumps(payload.chart_context, sort_keys=True, default=str),
                    created_at,
                    now,
                ),
            )
            row = connection.execute(
                "SELECT * FROM chart_orders WHERE chart_order_id = ? AND user_id = ?",
                (chart_order_id, user_id),
            ).fetchone()
            order_record = self._row_to_chart_order(row)
            self._append_chart_order_event_tx(
                connection,
                chart_order_id=chart_order_id,
                user_id=user_id,
                event_type="CHART_ORDER_SYNCED",
                payload=order_record,
                created_at=now,
            )
        return order_record

    def list_chart_orders(self, *, user_id: str, symbol: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        normalized_limit = max(1, min(int(limit), 500))
        with self._session() as connection:
            if symbol:
                rows = connection.execute(
                    """
                    SELECT * FROM chart_orders
                    WHERE user_id = ? AND symbol = ?
                    ORDER BY last_updated DESC
                    LIMIT ?
                    """,
                    (user_id, symbol.upper(), normalized_limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM chart_orders
                    WHERE user_id = ?
                    ORDER BY last_updated DESC
                    LIMIT ?
                    """,
                    (user_id, normalized_limit),
                ).fetchall()
        return [self._row_to_chart_order(row) for row in rows]

    def claim_pending_chart_order_events(self, *, limit: int = 25) -> list[dict[str, Any]]:
        now = _now_iso()
        normalized_limit = max(1, min(int(limit), 100))
        with self._session() as connection:
            rows = connection.execute(
                """
                SELECT * FROM chart_order_events
                WHERE status = 'PENDING'
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (normalized_limit,),
            ).fetchall()
            event_ids = [row["event_id"] for row in rows]
            if event_ids:
                placeholders = ",".join("?" for _ in event_ids)
                connection.execute(
                    f"UPDATE chart_order_events SET status = 'CLAIMED', claimed_at = ? WHERE event_id IN ({placeholders})",
                    (now, *event_ids),
                )
                rows = connection.execute(
                    f"SELECT * FROM chart_order_events WHERE event_id IN ({placeholders}) ORDER BY created_at ASC",
                    event_ids,
                ).fetchall()
        return [self._row_to_chart_order_event(row) for row in rows]

    def complete_chart_order_event(self, *, event_id: str, error: str | None = None) -> None:
        now = _now_iso()
        status = "FAILED" if error else "COMPLETED"
        with self._session() as connection:
            connection.execute(
                """
                UPDATE chart_order_events
                SET status = ?, completed_at = ?, error = ?
                WHERE event_id = ?
                """,
                (status, now, error, event_id),
            )

    def latest_user_api_key_metadata(self, *, user_id: str, provider: str | None = None) -> dict[str, Any] | None:
        with self._session() as connection:
            if provider:
                row = connection.execute(
                    """
                    SELECT * FROM user_api_keys
                    WHERE user_id = ? AND provider = ? AND is_active = 1
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    (user_id, provider),
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT * FROM user_api_keys
                    WHERE user_id = ? AND is_active = 1
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    (user_id,),
                ).fetchone()
        return self._row_to_api_key(row) if row is not None else None

    def record_chart_order_testnet_action(
        self,
        *,
        event_id: str,
        order: dict[str, Any],
        mode: str,
        credential: dict[str, Any] | None,
        action_payload: dict[str, Any],
    ) -> dict[str, Any]:
        now = _now_iso()
        action_id = f"action_{uuid4().hex}"
        with self._session() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO chart_order_testnet_actions (
                    action_id, event_id, chart_order_id, user_id, mode, symbol, side,
                    action_type, price, quantity, is_ai_trailing, credential_provider,
                    credential_key_preview, action_payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    action_id,
                    event_id,
                    order["chart_order_id"],
                    order["user_id"],
                    mode,
                    order["symbol"],
                    order["side"],
                    action_payload.get("action_type", "SYNC_ORDER"),
                    order.get("limit_price") or order.get("stop_loss") or order.get("take_profit"),
                    order.get("quantity"),
                    int(bool(order.get("is_ai_trailing"))),
                    credential.get("provider") if credential else None,
                    credential.get("key_preview") if credential else None,
                    json.dumps(action_payload, sort_keys=True, default=str),
                    now,
                ),
            )
            row = connection.execute(
                "SELECT * FROM chart_order_testnet_actions WHERE event_id = ?",
                (event_id,),
            ).fetchone()
        return self._row_to_testnet_action(row)

    def list_chart_order_testnet_actions(self, *, user_id: str, limit: int = 100) -> list[dict[str, Any]]:
        normalized_limit = max(1, min(int(limit), 500))
        with self._session() as connection:
            rows = connection.execute(
                """
                SELECT * FROM chart_order_testnet_actions
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (user_id, normalized_limit),
            ).fetchall()
        return [self._row_to_testnet_action(row) for row in rows]

    def _append_chart_order_event_tx(
        self,
        connection: sqlite3.Connection,
        *,
        chart_order_id: str,
        user_id: str,
        event_type: str,
        payload: dict[str, Any],
        created_at: str,
    ) -> dict[str, Any]:
        event_id = f"chart_evt_{uuid4().hex}"
        connection.execute(
            """
            INSERT INTO chart_order_events (
                event_id, chart_order_id, user_id, event_type, status, payload_json, created_at
            ) VALUES (?, ?, ?, ?, 'PENDING', ?, ?)
            """,
            (
                event_id,
                chart_order_id,
                user_id,
                event_type,
                json.dumps(payload, sort_keys=True, default=str),
                created_at,
            ),
        )
        return {
            "event_id": event_id,
            "chart_order_id": chart_order_id,
            "user_id": user_id,
            "event_type": event_type,
            "status": "PENDING",
            "payload": payload,
            "created_at": created_at,
        }

    @staticmethod
    def _row_to_api_key(row: sqlite3.Row) -> dict[str, Any]:
        return dict(row)

    @staticmethod
    def _row_to_strategy(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "ai_strategy_id": row["ai_strategy_id"],
            "slug": row["slug"],
            "version": row["version"],
            "display_name": row["display_name"],
            "model_family": row["model_family"],
            "metrics": _loads(row["metrics_json"], {}),
            "risk_context": _loads(row["risk_context_json"], {}),
            "signal_context": _loads(row["signal_context_json"], {}),
            "last_signal_at": row["last_signal_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _row_to_chart_order(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "chart_order_id": row["chart_order_id"],
            "user_id": row["user_id"],
            "ai_strategy_id": row["ai_strategy_id"],
            "workspace_mode": row["workspace_mode"],
            "symbol": row["symbol"],
            "exchange": row["exchange"],
            "side": row["side"],
            "order_type": row["order_type"],
            "limit_price": row["limit_price"],
            "stop_loss": row["stop_loss"],
            "take_profit": row["take_profit"],
            "quantity": row["quantity"],
            "is_ai_trailing": bool(row["is_ai_trailing"]),
            "status": row["status"],
            "client_revision": row["client_revision"],
            "chart_context": _loads(row["chart_context_json"], {}),
            "created_at": row["created_at"],
            "last_updated": row["last_updated"],
        }

    @staticmethod
    def _row_to_chart_order_event(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "event_id": row["event_id"],
            "chart_order_id": row["chart_order_id"],
            "user_id": row["user_id"],
            "event_type": row["event_type"],
            "status": row["status"],
            "payload": _loads(row["payload_json"], {}),
            "created_at": row["created_at"],
            "claimed_at": row["claimed_at"],
            "completed_at": row["completed_at"],
            "error": row["error"],
        }

    @staticmethod
    def _row_to_testnet_action(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "action_id": row["action_id"],
            "event_id": row["event_id"],
            "chart_order_id": row["chart_order_id"],
            "user_id": row["user_id"],
            "mode": row["mode"],
            "symbol": row["symbol"],
            "side": row["side"],
            "action_type": row["action_type"],
            "price": row["price"],
            "quantity": row["quantity"],
            "is_ai_trailing": bool(row["is_ai_trailing"]),
            "credential_provider": row["credential_provider"],
            "credential_key_preview": row["credential_key_preview"],
            "action_payload": _loads(row["action_payload_json"], {}),
            "created_at": row["created_at"],
        }


_repository: AdvancedTradingStateRepository | None = None


def get_advanced_trading_state_repository() -> AdvancedTradingStateRepository:
    global _repository
    if _repository is None:
        settings = get_settings()
        _repository = AdvancedTradingStateRepository(settings.pro_storage_path)
    return _repository


def reset_advanced_trading_state_repository() -> None:
    global _repository
    _repository = None
