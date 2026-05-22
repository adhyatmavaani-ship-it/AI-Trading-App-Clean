from contextlib import contextmanager
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings  # noqa: E402
from db.database import SQLiteTradeDatabase  # noqa: E402


class ProSQLiteStorageTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "pro.sqlite3"
        self.db = SQLiteTradeDatabase(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_bootstrap_creates_phase_9_tables(self):
        expected = {
            "strategy_marketplace",
            "pro_scanner_rules",
            "ai_copilot_history",
            "automated_journal_reports",
            "execution_requests",
            "broker_order_acknowledgements",
            "reconciliation_snapshots",
            "execution_audit_events",
        }
        self.assertTrue(expected.issubset(self.db.pro_feature_table_names()))

    def test_default_pro_storage_path_is_local_sandbox(self):
        self.assertEqual(Settings().pro_storage_path, "app_data/sandbox.db")

    def test_sqlite_uses_wal_and_busy_timeout_for_concurrent_reads(self):
        connection = self.db._connect()
        try:
            journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
            busy_timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]
        finally:
            connection.close()

        self.assertEqual(str(journal_mode).lower(), "wal")
        self.assertGreaterEqual(int(busy_timeout), 30000)

        self.db.append_ai_copilot_history(
            user_id="alice",
            session_id="session-1",
            role="user",
            message="committed message",
            grounded_ticker="BTCUSDT",
            metadata={},
        )
        writer = self.db._connect()
        try:
            writer.execute("BEGIN IMMEDIATE")
            writer.execute(
                """
                INSERT INTO ai_copilot_history (
                    user_id,
                    session_id,
                    role,
                    message,
                    grounded_ticker
                ) VALUES (?, ?, ?, ?, ?)
                """,
                ("alice", "session-1", "assistant", "uncommitted message", "BTCUSDT"),
            )

            rows = self.db.list_ai_copilot_history(user_id="alice", session_id="session-1")

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["message"], "committed message")
        finally:
            writer.rollback()
            writer.close()

    def test_strategy_marketplace_persists_ledger_record(self):
        self.db.save_strategy_marketplace_record(
            {
                "strategy_id": "strat_test",
                "publisher_user_id": "alice",
                "name": "Ledger Breakout",
                "style": "trend_following",
                "markets": ["BTCUSDT"],
                "evidence_type": "paper_ledger",
                "metrics": {
                    "trade_count": 20,
                    "win_rate": 0.62,
                    "profit_factor": 1.8,
                    "max_drawdown": 0.05,
                },
                "verified": True,
                "published_at": "2026-05-23T08:00:00+00:00",
            }
        )

        records = self.db.list_strategy_marketplace_records()

        self.assertEqual(records[0]["strategy_id"], "strat_test")
        self.assertEqual(records[0]["metrics"]["trade_count"], 20)
        self.assertEqual(records[0]["markets"], ["BTCUSDT"])

    def test_scanner_copilot_and_journal_records_are_queryable_after_reopen(self):
        self.db.save_pro_scanner_rule(
            rule_id="scan_test",
            user_id="alice",
            rule_name="RSI below 30",
            timeframe="1h",
            symbols=["BTCUSDT"],
            criteria=[{"field": "rsi", "operator": "below", "value": 30}],
            webhook_url="https://example.com/hook",
            match_count=2,
        )
        self.db.append_ai_copilot_history(
            user_id="alice",
            session_id="session-1",
            role="user",
            message="support on BTC?",
            grounded_ticker="BTCUSDT",
            metadata={"timeframe": "1h"},
        )
        self.db.save_automated_journal_report(
            {
                "report_id": "journal_test",
                "user_id": "alice",
                "symbol": "BTCUSDT",
                "pnl": -50.0,
                "psychology_tags": ["late_loser_exit"],
                "snapshot_image": {"data_url": "data:image/svg+xml;base64,abc"},
                "analysis": "Loss held too long.",
                "behavioral_summary": {"discipline_score": 80.0},
                "generated_at": "2026-05-23T09:00:00+00:00",
            },
            trade={
                "trade_id": "trade-1",
                "symbol": "BTCUSDT",
                "entry_price": 100.0,
                "exit_price": 95.0,
            },
        )

        reopened = SQLiteTradeDatabase(self.db_path)

        self.assertEqual(reopened.list_pro_scanner_rules(user_id="alice")[0]["id"], "scan_test")
        self.assertEqual(reopened.list_ai_copilot_history(user_id="alice", session_id="session-1")[0]["role"], "user")
        self.assertEqual(
            reopened.list_automated_journal_reports(user_id="alice")[0]["psychology_tags"],
            ["late_loser_exit"],
        )

    def test_user_controlled_phase_9_strings_are_bound_parameters(self):
        malicious_session = "session-x'); DROP TABLE ai_copilot_history; --"
        malicious_message = "hello'); DROP TABLE strategy_marketplace; --"
        malicious_webhook = "https://example.com/hook'); DROP TABLE pro_scanner_rules; --"
        malicious_criteria = "bullish'); DROP TABLE automated_journal_reports; --"

        self.db.append_ai_copilot_history(
            user_id="alice",
            session_id=malicious_session,
            role="user",
            message=malicious_message,
            grounded_ticker="BTCUSDT",
            metadata={"raw": malicious_message},
        )
        self.db.save_pro_scanner_rule(
            rule_id="scan_injection",
            user_id="alice",
            rule_name="Injection probe",
            timeframe="1h",
            symbols=["BTCUSDT"],
            criteria=[
                {
                    "field": "macd_crossover",
                    "operator": "equals",
                    "value": malicious_criteria,
                }
            ],
            webhook_url=malicious_webhook,
            match_count=0,
        )

        self.assertTrue(
            {
                "strategy_marketplace",
                "pro_scanner_rules",
                "ai_copilot_history",
                "automated_journal_reports",
            }.issubset(self.db.pro_feature_table_names())
        )
        self.assertEqual(
            self.db.list_ai_copilot_history(user_id="alice", session_id=malicious_session)[0]["message"],
            malicious_message,
        )
        rule = self.db.list_pro_scanner_rules(user_id="alice")[0]
        self.assertEqual(rule["webhook_url"], malicious_webhook)
        self.assertEqual(rule["criteria"][0]["value"], malicious_criteria)

    def test_automated_journal_trade_id_is_upserted_as_single_report(self):
        self.db.save_automated_journal_report(
            {
                "report_id": "journal_test",
                "user_id": "alice",
                "symbol": "BTCUSDT",
                "snapshot_image": {"data_url": "data:image/svg+xml;base64,abc"},
            },
            trade={"trade_id": "trade-1", "entry_price": 100.0, "exit_price": 101.0},
        )

        self.db.save_automated_journal_report(
            {
                "report_id": "journal_test_2",
                "user_id": "alice",
                "symbol": "BTCUSDT",
                "snapshot_image": {"data_url": "data:image/svg+xml;base64,def"},
            },
            trade={"trade_id": "trade-1", "entry_price": 100.0, "exit_price": 99.0},
        )

        reports = self.db.list_automated_journal_reports(user_id="alice")

        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["id"], "journal_test_2")

    def test_execution_request_idempotency_is_unique_and_recovers_after_reopen(self):
        first = self.db.claim_execution_request(
            execution_request_id="exec_1",
            idempotency_key_hash="hash_1",
            request_payload={"user_id": "alice", "symbol": "BTCUSDT", "side": "BUY", "signal_id": "exec_1"},
            execution_origin="api-test",
        )
        duplicate = self.db.claim_execution_request(
            execution_request_id="exec_1",
            idempotency_key_hash="hash_1",
            request_payload={"user_id": "alice", "symbol": "BTCUSDT", "side": "BUY", "signal_id": "exec_1"},
            execution_origin="api-retry",
        )
        self.db.update_execution_request_status(
            "exec_1",
            status="FILLED",
            trade_id="trade-1",
            response={
                "trade_id": "trade-1",
                "status": "EXECUTED",
                "trading_mode": "live",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "executed_price": 100.0,
                "executed_quantity": 1.0,
                "stop_loss": 95.0,
                "trailing_stop_pct": 0.004,
                "take_profit": 110.0,
                "fee_paid": 0.1,
                "slippage_bps": 10.0,
                "filled_ratio": 1.0,
            },
        )

        reopened = SQLiteTradeDatabase(self.db_path)
        recovered = reopened.execution_request_by_id("exec_1")

        self.assertTrue(first["claimed"])
        self.assertFalse(duplicate["claimed"])
        self.assertEqual(duplicate["execution_attempt"], 2)
        self.assertEqual(recovered["status"], "FILLED")
        self.assertIn("trade-1", recovered["response_json"])

    def test_broker_ack_and_reconciliation_snapshot_are_durable(self):
        ack = self.db.record_broker_acknowledgement(
            client_order_id="APP_AI_BRK_BTCUSDT_EXEC1",
            execution_request_id="exec_1",
            broker_order_id="broker-1",
            exchange="binance",
            symbol="BTCUSDT",
            side="BUY",
            status="FILLED",
            ack_payload={"orderId": "broker-1", "status": "FILLED"},
        )
        duplicate = self.db.record_broker_acknowledgement(
            client_order_id="APP_AI_BRK_BTCUSDT_EXEC1",
            execution_request_id="exec_1",
            broker_order_id="broker-1",
            exchange="binance",
            symbol="BTCUSDT",
            side="BUY",
            status="FILLED",
            ack_payload={"orderId": "broker-1", "status": "FILLED"},
        )
        self.db.save_reconciliation_snapshot(
            {
                "checked_at": "2026-05-23T10:00:00+00:00",
                "local_active": 1,
                "broker_active": 1,
                "mismatch_count": 0,
                "duplicate_ack_count": 1,
            }
        )

        reopened = SQLiteTradeDatabase(self.db_path)
        recovered_ack = reopened.broker_acknowledgement_by_client_order_id("APP_AI_BRK_BTCUSDT_EXEC1")
        snapshot = reopened.latest_reconciliation_snapshot()

        self.assertFalse(ack["duplicate"])
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(recovered_ack["duplicate_count"], 1)
        self.assertEqual(recovered_ack["ack"]["orderId"], "broker-1")
        self.assertEqual(snapshot["duplicate_ack_count"], 1)

    def test_execution_audit_events_are_append_only_and_ordered(self):
        first = self.db.append_execution_audit_event(
            "exec_audit",
            "execution_requested",
            {"symbol": "BTCUSDT"},
        )
        second = self.db.append_execution_audit_event(
            "exec_audit",
            "risk_shield_decision",
            {"approved": True},
        )

        events = self.db.execution_audit_events("exec_audit")

        self.assertLess(first["id"], second["id"])
        self.assertEqual([event["event_type"] for event in events], ["execution_requested", "risk_shield_decision"])
        self.assertEqual(events[1]["payload"]["approved"], True)

    def test_recovery_metadata_is_durable(self):
        self.db.claim_execution_request(
            execution_request_id="exec_recovery",
            idempotency_key_hash="hash_recovery",
            request_payload={"user_id": "alice", "symbol": "ETHUSDT", "side": "BUY", "signal_id": "exec_recovery"},
            execution_origin="api-test",
        )
        self.db.update_execution_request_status("exec_recovery", status="SUBMITTED")

        updated = self.db.mark_execution_recovery_checked(
            "exec_recovery",
            recovery_reason="submitted_unacknowledged,stale_inflight_execution",
        )
        reopened = SQLiteTradeDatabase(self.db_path)
        recovered = reopened.execution_request_by_id("exec_recovery")

        self.assertEqual(updated["recovery_attempts"], 1)
        self.assertEqual(recovered["recovery_reason"], "submitted_unacknowledged,stale_inflight_execution")
        self.assertIsNotNone(recovered["recovery_last_checked_at"])

    def test_sqlite_lock_retry_updates_pressure_metrics(self):
        original_session = self.db._session
        attempts = {"count": 0}

        @contextmanager
        def flaky_session(*, operation_name="sqlite_transaction"):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise sqlite3.OperationalError("database is locked")
            with original_session(operation_name=operation_name) as connection:
                yield connection

        self.db._session = flaky_session
        try:
            self.db.append_execution_audit_event("exec_retry", "execution_requested", {})
        finally:
            self.db._session = original_session

        pressure = self.db.db_write_pressure()
        self.assertEqual(attempts["count"], 2)
        self.assertGreaterEqual(pressure["retry_count"], 1)


if __name__ == "__main__":
    unittest.main()
