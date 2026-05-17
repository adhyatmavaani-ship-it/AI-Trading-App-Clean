import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.operational_readiness import OperationalReadinessEngine  # noqa: E402


class Phase10ReadinessConsolidationTest(unittest.TestCase):
    def test_readiness_engine_marks_clean_stack_ready(self):
        result = OperationalReadinessEngine().evaluate(
            slo={"mode": "NORMAL"},
            release={"status": "READY", "production_rollout_allowed": True},
            compliance={"state": "COMPLIANT"},
            disaster_recovery={"state": "READY"},
            config_drift={"state": "IN_POLICY"},
            backup={"status": "READY"},
        )

        self.assertEqual(result["status"], "READY")
        self.assertTrue(result["safe_for_release"])
        self.assertTrue(result["advisory_only"])

    def test_readiness_engine_blocks_degraded_stack(self):
        result = OperationalReadinessEngine().evaluate(
            slo={"mode": "INCIDENT"},
            release={"status": "BLOCKED", "production_rollout_allowed": False},
            compliance={"state": "REVIEW"},
            disaster_recovery={"state": "ATTENTION"},
            config_drift={"state": "DRIFT"},
            backup={"status": "ATTENTION"},
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["safe_for_release"])
        self.assertGreaterEqual(len(result["actions"]), 4)


if __name__ == "__main__":
    unittest.main()
