from __future__ import annotations

from datetime import datetime, timezone
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings  # noqa: E402
from app.services.event_dispatcher import EventDispatcher  # noqa: E402
from app.services.execution_storage import POSTGRES_COMPATIBILITY_HELPERS, POSTGRES_COMPAT_SQL  # noqa: E402
from app.services.redis_cache import RedisCache  # noqa: E402
from app.services.safety_state import SafetyStateService  # noqa: E402
from app.services.source_of_truth import classify_reconciliation_conflict, reconciliation_confidence_score  # noqa: E402
from db.database import SQLiteTradeDatabase  # noqa: E402


class OperationalInfrastructureHardeningTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = SQLiteTradeDatabase(Path(self.temp_dir.name) / "ops.sqlite3")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_source_of_truth_conflict_prefers_broker_over_stale_local_state(self):
        decision = classify_reconciliation_conflict(
            local_trade={"trade_id": "t1", "symbol": "BTCUSDT", "status": "SUBMITTED"},
            broker_position=None,
            broker_acknowledgements=[],
            checked_at="2026-05-23T00:00:00+00:00",
        ).to_payload()

        self.assertEqual(decision["winning_source"], "broker_position")
        self.assertEqual(decision["losing_source"], "local_execution")
        self.assertEqual(decision["conflict_type"], "broker_position_overrides_stale_local_state")
        self.assertGreater(decision["winning_authority_rank"], decision["losing_authority_rank"])

    def test_reconciliation_confidence_scoring_is_deterministic(self):
        healthy = reconciliation_confidence_score(mismatch_count=0, duplicate_ack_count=0)
        degraded = reconciliation_confidence_score(mismatch_count=2, duplicate_ack_count=1, snapshot_regression=True)

        self.assertEqual(healthy, 1.0)
        self.assertLess(degraded, healthy)
        self.assertEqual(degraded, reconciliation_confidence_score(mismatch_count=2, duplicate_ack_count=1, snapshot_regression=True))

    def test_replay_ambiguity_records_operational_incident(self):
        self.db.append_execution_audit_event("exec_replay_ambiguous", "execution_requested", {"step": 1})
        self.db.append_execution_audit_event("exec_replay_ambiguous", "validation_passed", {"step": 2})
        connection = self.db._connect()
        try:
            first = connection.execute(
                """
                SELECT event_sequence
                FROM execution_event_outbox
                WHERE execution_request_id = ?
                ORDER BY id ASC
                LIMIT 1
                """,
                ("exec_replay_ambiguous",),
            ).fetchone()
            connection.execute(
                """
                UPDATE execution_event_outbox
                SET event_sequence = ?
                WHERE execution_request_id = ? AND event_type = 'validation_passed'
                """,
                (int(first["event_sequence"]), "exec_replay_ambiguous"),
            )
            connection.commit()
        finally:
            connection.close()

        result = self.db.validate_execution_replay_order("exec_replay_ambiguous")
        incidents = self.db.operational_incident_counts()

        self.assertFalse(result["consistent"])
        self.assertEqual(incidents["by_type"]["replay_ordering_violation"], 1)

    def test_dispatcher_heartbeat_clears_stall_and_reports_backpressure(self):
        cache = RedisCache("")
        self.db.append_execution_audit_event("exec_dispatch_pressure", "execution_requested", {})
        self.db.append_execution_audit_event("exec_dispatch_pressure_2", "execution_requested", {})
        dispatcher = EventDispatcher(
            store=self.db,
            cache=cache,
            worker_id="dispatcher-unit",
            batch_size=1,
            backlog_warning_threshold=1,
            backlog_critical_threshold=10,
            stall_seconds=30,
        )

        before = dispatcher.status()
        result = dispatcher.dispatch_once()
        after = dispatcher.status()
        cached_outbox = cache.get_json("monitor:execution_event_outbox")

        self.assertTrue(before["stalled"])
        self.assertFalse(after["stalled"])
        self.assertEqual(result["backpressure"], 1)
        self.assertEqual(cached_outbox["severity"], "WARNING")

    def test_poison_dispatch_escalates_to_dead_letter_incident(self):
        self.db.append_execution_audit_event("exec_poison_incident", "execution_requested", {})

        def poison_hook(event):
            raise RuntimeError("poison event")

        dispatcher = EventDispatcher(
            store=self.db,
            worker_id="dispatcher-poison",
            max_attempts=1,
            base_retry_delay_seconds=0,
            notification_hooks=[poison_hook],
        )

        result = dispatcher.dispatch_once()
        incidents = self.db.operational_incident_counts()
        dead_letters = self.db.dead_letter_outbox_events()

        self.assertEqual(result["failed"], 1)
        self.assertEqual(dead_letters[0]["delivery_status"], "DEAD_LETTER")
        self.assertEqual(incidents["by_type"]["poison_event_detection"], 1)

    def test_operational_health_snapshot_exposes_flutter_safe_infrastructure_fields(self):
        cache = RedisCache("")
        now = datetime.now(timezone.utc).isoformat()
        cache.set("monitor:websocket_connected", "1", ttl=60)
        cache.set("monitor:websocket_connected:last_seen_ts", now, ttl=60)
        cache.set_json("market:feed:health", {"healthy": True, "producer_last_seen_ts": now}, ttl=60)
        cache.set_json(
            "broker:reconciliation:last",
            {"mismatch_count": 0, "duplicate_ack_count": 0, "confidence_score": 0.91, "producer_last_seen_ts": now},
            ttl=60,
        )
        cache.set_json("ai:latency", {"latency_ms": 10.0, "producer_last_seen_ts": now}, ttl=60)
        cache.set_json("exchange:latency", {"latency_ms": 10.0, "producer_last_seen_ts": now}, ttl=60)
        self.db.append_operational_incident(
            incident_type="lease_conflict",
            severity="MEDIUM",
            message="unit test",
            execution_request_id="exec_health",
        )
        service = SafetyStateService(settings=Settings(redis_url=""), cache=cache, store=self.db)

        payload = service.snapshot(trading_mode="live")

        self.assertTrue(payload["execution_available"])
        self.assertIn("dispatcher_status", payload)
        self.assertEqual(payload["reconciliation_confidence"]["score"], 0.91)
        self.assertEqual(payload["incident_counts"]["by_type"]["lease_conflict"], 1)
        self.assertEqual(payload["lease_conflict_counts"]["incident_total"], 1)
        self.assertIn(payload["outbox_backlog_severity"], {"OK", "WARNING", "CRITICAL"})

    def test_postgresql_compatibility_helpers_centralize_operational_primitives(self):
        self.assertIn("FOR UPDATE SKIP LOCKED", POSTGRES_COMPAT_SQL["claim_outbox_events"])
        self.assertIn("RETURNING", POSTGRES_COMPAT_SQL["acquire_execution_lease"])
        self.assertIn("append_operational_incident", POSTGRES_COMPAT_SQL)
        self.assertEqual(
            POSTGRES_COMPATIBILITY_HELPERS["replay_query_semantics"]["event_order"],
            "ORDER BY event_sequence ASC, id ASC",
        )


if __name__ == "__main__":
    unittest.main()
