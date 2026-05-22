from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings  # noqa: E402
from app.core.exceptions import StateError  # noqa: E402
from app.schemas.trading import TradeRequest  # noqa: E402
from app.services.execution_idempotency import ExecutionIdempotencyService  # noqa: E402
from app.services.redis_cache import RedisCache  # noqa: E402
from db.database import SQLiteTradeDatabase  # noqa: E402


class ExecutionIdempotencyServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "execution.sqlite3"
        self.store = SQLiteTradeDatabase(self.db_path)
        self.cache = RedisCache("")
        self.service = ExecutionIdempotencyService(
            settings=Settings(redis_url="", execution_idempotency_ttl_seconds=60),
            cache=self.cache,
            store=self.store,
        )
        self.request = TradeRequest(
            user_id="alice",
            symbol="BTCUSDT",
            side="BUY",
            quantity=1.0,
            confidence=0.8,
            reason="unit-test",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_claim_generates_stable_execution_request_id_and_signal_id(self):
        first = self.service.claim(
            self.request,
            idempotency_key="client-key-1",
            origin="api-test",
            trading_mode="live",
        )

        self.assertTrue(first.execution_request_id.startswith("exec_"))
        self.assertEqual(first.request.signal_id, first.execution_request_id)
        self.assertEqual(first.execution_attempt, 1)
        events = self.store.execution_audit_events(first.execution_request_id)
        self.assertEqual(events[0]["event_type"], "execution_requested")

    def test_duplicate_live_claim_is_blocked_until_replay_exists(self):
        first = self.service.claim(
            self.request,
            idempotency_key="client-key-2",
            origin="api-test",
            trading_mode="live",
        )

        with self.assertRaises(StateError):
            self.service.claim(
                self.request,
                idempotency_key="client-key-2",
                origin="api-test",
                trading_mode="live",
            )
        self.assertEqual(int(self.cache.get("monitor:duplicate_execution_prevented") or 0), 1)
        self.assertEqual(first.execution_attempt, 1)

    def test_completed_execution_replays_same_response(self):
        first = self.service.claim(
            self.request,
            idempotency_key="client-key-3",
            origin="api-test",
            trading_mode="live",
        )
        self.service.complete(
            first,
            {
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

        duplicate = self.service.claim(
            self.request,
            idempotency_key="client-key-3",
            origin="api-test",
            trading_mode="live",
        )

        self.assertIsNotNone(duplicate.replay_response)
        self.assertEqual(duplicate.replay_response.trade_id, "trade-1")
        self.assertTrue(duplicate.replay_response.duplicate_signal)

    def test_completed_execution_replays_after_cache_restart(self):
        first = self.service.claim(
            self.request,
            idempotency_key="client-key-restart",
            origin="api-test",
            trading_mode="live",
        )
        self.service.complete(
            first,
            {
                "trade_id": "trade-restart",
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
        restarted = ExecutionIdempotencyService(
            settings=Settings(redis_url="", execution_idempotency_ttl_seconds=60),
            cache=RedisCache(""),
            store=SQLiteTradeDatabase(self.db_path),
        )

        duplicate = restarted.claim(
            self.request,
            idempotency_key="client-key-restart",
            origin="api-test",
            trading_mode="live",
        )

        self.assertIsNotNone(duplicate.replay_response)
        self.assertEqual(duplicate.replay_response.trade_id, "trade-restart")

    def test_lifecycle_audit_records_validation_submission_and_resolution(self):
        claim = self.service.claim(
            self.request,
            idempotency_key="client-key-audit",
            origin="api-test",
            trading_mode="live",
        )
        self.service.mark_validated(claim)
        self.service.mark_submitted(claim)
        self.service.complete(
            claim,
            {
                "trade_id": "trade-audit",
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

        events = [event["event_type"] for event in self.store.execution_audit_events(claim.execution_request_id)]

        self.assertIn("execution_requested", events)
        self.assertIn("validation_passed", events)
        self.assertIn("broker_submit", events)
        self.assertIn("execution_resolved", events)


if __name__ == "__main__":
    unittest.main()
