import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.model_registry import ModelRegistry


class ModelRegistryPromotionTest(unittest.TestCase):
    def test_promotion_writes_registry_and_version_snapshots(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = ModelRegistry(Settings(redis_url="redis://unused", model_dir=tmpdir))
            registry.promote_probability_model(
                {"model": "v1"},
                {"scaler": "v1"},
                {
                    "model_version": "prob-v1",
                    "training_samples": 80,
                    "validation_samples": 20,
                    "recent_validation_accuracy_lift": 0.07,
                    "trigger_mode": "batch",
                },
            )
            registry.promote_probability_model(
                {"model": "v2"},
                {"scaler": "v2"},
                {
                    "model_version": "prob-v2",
                    "training_samples": 95,
                    "validation_samples": 20,
                    "recent_validation_accuracy_lift": 0.08,
                    "trigger_mode": "emergency",
                },
            )

            latest_metadata = registry.load_probability_metadata()
            registry_payload = registry.load_probability_registry()
            version_dir = Path(tmpdir) / "probability_versions" / "prob-v1"

            self.assertEqual(latest_metadata["model_version"], "prob-v2")
            self.assertEqual(len(registry_payload["events"]), 2)
            self.assertEqual(registry_payload["events"][-1]["model_version"], "prob-v2")
            self.assertTrue(version_dir.exists())
            self.assertTrue((version_dir / "trade_probability_metadata.json").exists())
            self.assertTrue((Path(tmpdir) / "trade_probability_model_fallback.joblib").exists())


if __name__ == "__main__":
    unittest.main()
