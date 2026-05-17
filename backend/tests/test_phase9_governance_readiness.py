import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.compliance_governance import ComplianceGovernanceEngine  # noqa: E402
from app.services.config_drift import ConfigDriftDetector  # noqa: E402
from app.services.data_lineage import DataLineageManifest  # noqa: E402
from app.services.disaster_recovery import DisasterRecoveryPlanner  # noqa: E402
from app.services.synthetic_probe import SyntheticProbePlanner  # noqa: E402


class Phase9GovernanceReadinessTest(unittest.TestCase):
    def test_config_drift_detects_unsafe_operational_state(self):
        drift = ConfigDriftDetector().detect(
            redis_enabled=False,
            redis_fallback=True,
            release={"status": "BLOCKED"},
            backup={"status": "ATTENTION"},
            replay_checkpoint={"valid": False},
        )

        self.assertEqual(drift["state"], "DRIFT")
        self.assertGreaterEqual(drift["drift_count"], 4)
        self.assertFalse(drift["rollback_safe"])

    def test_synthetic_probe_planner_heightens_when_release_not_ready(self):
        probes = SyntheticProbePlanner().plan(
            release={"status": "BLOCKED"},
            slo={"mode": "INCIDENT"},
        )

        self.assertEqual(probes["mode"], "HEIGHTENED")
        self.assertEqual(probes["interval_seconds"], 10)
        self.assertGreaterEqual(len(probes["probes"]), 4)

    def test_disaster_recovery_requires_drill_without_checkpoint(self):
        plan = DisasterRecoveryPlanner().plan(
            backup={"status": "READY"},
            replay_checkpoint={"valid": False},
            capacity={"scale_mode": "HOLD"},
            incident={"severity": "P2"},
        )

        self.assertEqual(plan["state"], "ATTENTION")
        self.assertTrue(plan["drill_required"])
        self.assertGreaterEqual(plan["rpo_seconds"], 300)

    def test_lineage_and_compliance_are_metadata_only(self):
        lineage = DataLineageManifest().build(
            audit={"manifest_version": "ops-audit-v1"},
            release={"status": "READY"},
        )
        compliance = ComplianceGovernanceEngine().evaluate(
            drift={"state": "IN_POLICY"},
            lineage=lineage,
            audit={"manifest_version": "ops-audit-v1"},
            backup={"status": "READY"},
        )

        self.assertFalse(lineage["contains_secrets"])
        self.assertEqual(compliance["state"], "COMPLIANT")
        self.assertIn("runbook steps require an operator", compliance["controls"])


if __name__ == "__main__":
    unittest.main()
