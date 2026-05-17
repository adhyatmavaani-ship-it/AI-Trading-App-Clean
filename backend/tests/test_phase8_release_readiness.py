import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.audit_export import AuditExportPlanner  # noqa: E402
from app.services.backup_readiness import BackupReadinessPlanner  # noqa: E402
from app.services.canary_planner import CanaryPlanner  # noqa: E402
from app.services.release_readiness import ReleaseReadinessEngine  # noqa: E402
from app.services.rollback_planner import RollbackPlanner  # noqa: E402


class Phase8ReleaseReadinessTest(unittest.TestCase):
    def test_release_readiness_blocks_on_critical_state(self):
        result = ReleaseReadinessEngine().evaluate(
            slo={"mode": "INCIDENT"},
            incident={"status": "OPEN"},
            replay_checkpoint={"valid": False},
            capacity={"scale_mode": "SCALE_OUT"},
            redis_fallback=True,
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["production_rollout_allowed"])
        self.assertGreaterEqual(len(result["blockers"]), 4)

    def test_canary_planner_disables_when_release_blocked(self):
        plan = CanaryPlanner().plan(
            release={"canary_allowed": False},
            capacity={"scale_mode": "HOLD"},
        )

        self.assertEqual(plan["mode"], "DISABLED")
        self.assertEqual(plan["traffic_steps"], [])

    def test_canary_planner_uses_conservative_steps_under_capacity_pressure(self):
        plan = CanaryPlanner().plan(
            release={"canary_allowed": True},
            capacity={"scale_mode": "SCALE_OUT"},
        )

        self.assertEqual(plan["mode"], "CONSERVATIVE")
        self.assertEqual(plan["traffic_steps"], [1, 5, 10])

    def test_rollback_and_backup_plans_are_manual_and_safe(self):
        rollback = RollbackPlanner().plan(
            release={"status": "BLOCKED"},
            incident={"severity": "P1"},
        )
        backup = BackupReadinessPlanner().plan(
            replay_checkpoint={"valid": True},
            retention={"mode": "STANDARD"},
        )

        self.assertTrue(rollback["recommended"])
        self.assertIn("do not alter execution/risk/auth/paper-live configuration during rollback", rollback["steps"])
        self.assertEqual(backup["status"], "READY")
        self.assertIn("do not compact risk decision audit records", backup["exclusions"])

    def test_audit_export_manifest_is_metadata_only(self):
        manifest = AuditExportPlanner().build_manifest(
            incident={"severity": "P2"},
            release={"status": "MANUAL_REVIEW"},
            runbook={"steps": ["verify health"]},
        )

        self.assertEqual(manifest["manifest_version"], "ops-audit-v1")
        self.assertEqual(manifest["runbook_step_count"], 1)
        self.assertIn("no secrets", manifest["privacy"])


if __name__ == "__main__":
    unittest.main()
