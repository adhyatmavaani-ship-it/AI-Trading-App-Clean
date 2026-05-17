import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.capacity_planner import CapacityPlanner  # noqa: E402
from app.services.incident_response import IncidentResponseEngine  # noqa: E402
from app.services.retention_policy import RetentionPolicyPlanner  # noqa: E402
from app.services.runbook_orchestrator import RunbookOrchestrator  # noqa: E402


class Phase7OperationalReadinessTest(unittest.TestCase):
    def test_incident_response_escalates_with_slo_and_replay_state(self):
        incident = IncidentResponseEngine().snapshot(
            slo={
                "mode": "INCIDENT",
                "breaches": [{"code": "sequence_gaps"}],
                "actions": ["force snapshot resume and pause stale chart rendering"],
            },
            high_availability={"mode": "DEGRADED", "actions": ["scale workers"]},
            replay_checkpoint={"valid": False},
            redis_fallback=False,
        )

        self.assertEqual(incident["severity"], "P0")
        self.assertEqual(incident["status"], "OPEN")
        self.assertTrue(incident["requires_human"])
        self.assertIn("create fresh chart snapshot checkpoint before replay-dependent debugging", incident["runbook"])

    def test_retention_policy_selects_aggressive_mode_under_pressure(self):
        plan = RetentionPolicyPlanner().plan(
            event_count=180_000,
            replay_count=150_000,
            ai_context_count=80_000,
        )

        self.assertEqual(plan["mode"], "AGGRESSIVE")
        self.assertLessEqual(plan["hot_retention_days"], 3)
        self.assertIn("archive replay logs before destructive retention", plan["actions"])

    def test_capacity_planner_recommends_scale_out(self):
        plan = CapacityPlanner().recommend(
            active_websockets=2400,
            event_throughput=4500,
            ai_queue_depth=350,
            gpu_queue_depth=96,
            p95_latency_ms=820,
        )

        self.assertEqual(plan["scale_mode"], "SCALE_OUT")
        self.assertGreaterEqual(plan["websocket_instances"], 3)
        self.assertGreaterEqual(plan["ai_workers"], 4)
        self.assertGreaterEqual(plan["gpu_workers"], 3)

    def test_runbook_orchestrator_keeps_actions_manual(self):
        runbook = RunbookOrchestrator().build(
            incident={"runbook": ["force snapshot resume"], "severity": "P1"},
            capacity={
                "scale_mode": "SCALE_OUT",
                "websocket_instances": 3,
                "ai_workers": 4,
                "gpu_workers": 2,
            },
            retention={"mode": "BALANCED"},
        )

        self.assertFalse(runbook["safe_to_auto_apply"])
        self.assertTrue(runbook["operator_required"])
        self.assertIn("scale websocket=3 ai=4 gpu=2", runbook["steps"])


if __name__ == "__main__":
    unittest.main()
