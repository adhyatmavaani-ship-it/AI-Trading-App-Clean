from datetime import datetime, timedelta, timezone
import unittest
import sys
import tempfile
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.broker_reconciliation import BrokerReconciliationEngine
from app.services.broker_security import BrokerCredentialVault
from app.services.execution_engine import ExecutionEngine
from db.database import SQLiteTradeDatabase


class InMemoryCache:
    def __init__(self):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ttl=None):
        self.store[key] = value

    def set_json(self, key, value, ttl=None):
        self.store[key] = value

    def increment(self, key, ttl=None):
        self.store[key] = int(self.store.get(key, 0)) + 1
        return self.store[key]


class FakeStateManager:
    def __init__(self):
        self.trades = [
            {"trade_id": "t1", "symbol": "BTCUSDT", "status": "OPEN"},
        ]

    def restore_active_trades(self):
        return list(self.trades)

    def save_active_trade(self, trade_id, payload):
        self.trades = [payload if item["trade_id"] == trade_id else item for item in self.trades]


class FakeExchangeClient:
    def __init__(self, positions=None):
        self.orders = []
        self.positions = positions

    def fetch_positions(self):
        if self.positions is not None:
            return list(self.positions)
        return [{"symbol": "BTCUSDT", "side": "BUY", "quantity": 0.5, "exchange": "binance"}]

    def create_order(self, **kwargs):
        self.orders.append(kwargs)
        return {
            "orderId": f"order-{len(self.orders)}",
            "status": "FILLED",
            "executedQty": f"{kwargs['quantity']:.8f}",
            "price": "100.0",
            "fills": [{"price": "100.0", "qty": f"{kwargs['quantity']:.8f}"}],
        }


class BrokerBridgeTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_vault_encrypts_and_rejects_withdraw_permission(self):
        vault = BrokerCredentialVault(Settings(broker_vault_master_key="unit-test-secret"))
        token = vault.encrypt_credentials(
            {"broker": "binance", "api_key": "k", "api_secret": "s", "permissions": ["read", "trade"]}
        )
        decoded = vault.decrypt_credentials(token)
        self.assertEqual(decoded["broker"], "binance")

        with self.assertRaises(ValueError):
            vault.encrypt_credentials({"broker": "binance", "permissions": ["read", "withdraw"]})

    def test_emergency_feed_freeze_sends_reduce_only_close_all(self):
        settings = Settings(
            trading_mode="paper",
            redis_url="redis://unused",
            broker_emergency_feed_freeze_seconds=10.0,
        )
        engine = ExecutionEngine(settings)
        fake_exchange = FakeExchangeClient()
        engine.exchange_clients = {"binance": fake_exchange}
        cache = InMemoryCache()
        cache.set(
            "market:feed:last_seen_ts",
            (datetime.now(timezone.utc) - timedelta(seconds=15)).isoformat(),
        )
        reconciler = BrokerReconciliationEngine(
            settings=settings,
            execution_engine=engine,
            redis_state_manager=FakeStateManager(),
            cache=cache,
        )

        result = reconciler.emergency_close_if_feed_frozen()

        self.assertTrue(result["triggered"])
        self.assertEqual(result["closed_count"], 1)
        self.assertTrue(fake_exchange.orders[0]["reduce_only"])
        self.assertTrue(result["orders"][0]["clientOrderId"].startswith("APP_AI_BRK_BTCUSDT_"))

    def test_reconciliation_detects_duplicate_broker_acknowledgements(self):
        settings = Settings(trading_mode="paper", redis_url="redis://unused")
        engine = ExecutionEngine(settings)
        engine.exchange_clients = {
            "binance": FakeExchangeClient(
                positions=[
                    {"symbol": "BTCUSDT", "clientOrderId": "APP_AI_BRK_BTCUSDT_DUP"},
                    {"symbol": "BTCUSDT", "clientOrderId": "APP_AI_BRK_BTCUSDT_DUP"},
                ]
            )
        }
        cache = InMemoryCache()
        store = SQLiteTradeDatabase(Path(self.temp_dir.name) / "reconcile.sqlite3")
        reconciler = BrokerReconciliationEngine(
            settings=settings,
            execution_engine=engine,
            redis_state_manager=FakeStateManager(),
            cache=cache,
            store=store,
        )

        result = reconciler.reconcile_once()
        startup = reconciler.startup_recovery_report()

        self.assertEqual(result["duplicate_ack_count"], 1)
        self.assertEqual(cache.store["monitor:broker_duplicate_ack_count"], 1)
        self.assertEqual(cache.store["broker:reconciliation:last"]["producer_age_ms"], 0.0)
        self.assertEqual(startup["latest_reconciliation"]["duplicate_ack_count"], 1)

    def test_startup_recovery_classifies_orphan_execution_without_closing_positions(self):
        settings = Settings(
            trading_mode="live",
            redis_url="redis://unused",
            execution_recovery_stale_seconds=0.0,
        )
        engine = ExecutionEngine(settings)
        fake_exchange = FakeExchangeClient()
        engine.exchange_clients = {"binance": fake_exchange}
        cache = InMemoryCache()
        store = SQLiteTradeDatabase(Path(self.temp_dir.name) / "recovery.sqlite3")
        store.claim_execution_request(
            execution_request_id="exec_orphan",
            idempotency_key_hash="hash_orphan",
            request_payload={"user_id": "alice", "symbol": "BTCUSDT", "side": "BUY", "signal_id": "exec_orphan"},
            execution_origin="api-test",
        )
        store.update_execution_request_status("exec_orphan", status="SUBMITTED")
        reconciler = BrokerReconciliationEngine(
            settings=settings,
            execution_engine=engine,
            redis_state_manager=FakeStateManager(),
            cache=cache,
            store=store,
        )

        startup = reconciler.startup_recovery_report()
        recovered = store.execution_request_by_id("exec_orphan")
        events = store.execution_audit_events("exec_orphan")

        self.assertEqual(startup["orphan_execution_count"], 1)
        self.assertFalse(startup["auto_close_performed"])
        self.assertIn("submitted_unacknowledged", startup["recovery_checks"][0]["recovery_reason"])
        self.assertIn("stale_inflight_execution", startup["recovery_checks"][0]["recovery_reason"])
        self.assertEqual(recovered["recovery_attempts"], 1)
        self.assertEqual(fake_exchange.orders, [])
        self.assertEqual(events[-1]["event_type"], "recovery_triggered")


if __name__ == "__main__":
    unittest.main()
