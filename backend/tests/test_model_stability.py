import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.model_stability import ModelStabilityService


class InMemoryCache:
    def __init__(self):
        self.store = {}

    def get_json(self, key):
        return self.store.get(key)

    def set_json(self, key, value, ttl):
        self.store[key] = value

    def increment(self, key, ttl):
        self.store[key] = int(self.store.get(key, 0)) + 1
        return self.store[key]

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ttl=None):
        self.store[key] = value


class StubRegistry:
    def __init__(self):
        self.active_metadata = {
            "model_version": "prob-v4",
            "positive_rate": 0.7,
            "calibration_error": 0.04,
            "feature_means": {
                "trend_strength": 0.8,
                "rsi": 55.0,
                "adx": 30.0,
            },
        }
        self.fallback_metadata = {
            "model_version": "prob-v3",
            "positive_rate": 0.61,
            "calibration_error": 0.03,
            "feature_means": {
                "trend_strength": 0.6,
                "rsi": 51.0,
                "adx": 22.0,
            },
        }
        self.fallback_activated = False

    def current_version(self):
        return self.active_metadata["model_version"]

    def load_probability_metadata(self):
        return self.active_metadata

    def load_probability_fallback_metadata(self):
        return self.fallback_metadata

    def activate_probability_fallback(self):
        self.fallback_activated = True
        self.active_metadata = dict(self.fallback_metadata)
        return self.active_metadata


class ModelStabilityServiceTest(unittest.TestCase):
    def test_high_calibration_drift_marks_model_degraded_and_switches_fallback(self):
        settings = Settings(
            probability_max_calibration_error=0.18,
            probability_concept_drift_threshold=0.18,
            probability_min_validation_samples=12,
        )
        cache = InMemoryCache()
        registry = StubRegistry()
        service = ModelStabilityService(settings=settings, registry=registry, cache=cache)

        status = None
        for _ in range(20):
            status = service.record_live_outcome(
                won=False,
                predicted_probability=0.92,
                feature_snapshot={"trend_strength": 0.82, "rsi": 56.0, "adx": 31.0},
                model_version="prob-v4",
            )

        self.assertIsNotNone(status)
        self.assertTrue(status.degraded)
        self.assertTrue(status.retraining_triggered)
        self.assertEqual(status.active_model_version, "prob-v3")
        self.assertTrue(registry.fallback_activated)
        self.assertGreaterEqual(status.calibration_error, settings.probability_max_calibration_error)

    def test_feature_drift_reduces_trading_frequency_before_full_degradation(self):
        settings = Settings(
            probability_feature_drift_threshold=0.20,
            probability_frequency_reduction_threshold=0.12,
            probability_reduced_trading_multiplier=0.5,
        )
        cache = InMemoryCache()
        registry = StubRegistry()
        service = ModelStabilityService(settings=settings, registry=registry, cache=cache)

        status = service.record_live_outcome(
            won=True,
            predicted_probability=0.71,
            feature_snapshot={"trend_strength": 0.05, "rsi": 40.0, "adx": 6.0},
            model_version="prob-v4",
        )

        self.assertFalse(status.degraded)
        self.assertTrue(status.retraining_triggered)
        self.assertEqual(status.trading_frequency_multiplier, 0.5)
        self.assertGreaterEqual(status.feature_drift_score, settings.probability_frequency_reduction_threshold)

    def test_concentration_drift_softens_trading_frequency(self):
        settings = Settings(
            probability_concentration_drift_threshold=0.10,
            probability_concentration_reduction_threshold=0.06,
            probability_reduced_trading_multiplier=0.5,
        )
        cache = InMemoryCache()
        registry = StubRegistry()
        service = ModelStabilityService(settings=settings, registry=registry, cache=cache)

        status = service.update_concentration_state(
            {
                "gross_exposure_drift": 0.03,
                "cluster_concentration_drift": 0.07,
                "beta_bucket_concentration_drift": 0.04,
                "cluster_turnover": 0.12,
            }
        )

        self.assertFalse(status.degraded)
        self.assertEqual(status.trading_frequency_multiplier, 0.5)
        self.assertAlmostEqual(status.concentration_drift_score, 0.12, places=6)
        self.assertTrue(status.retraining_triggered)
        history = service.concentration_history()
        self.assertEqual(len(history), 1)
        self.assertAlmostEqual(history[0]["score"], 0.12, places=6)

    def test_sleeve_budget_stress_updates_concentration_history_and_softens_trading(self):
        settings = Settings(
            probability_concentration_drift_threshold=0.10,
            probability_concentration_reduction_threshold=0.06,
            probability_reduced_trading_multiplier=0.5,
            portfolio_concentration_soft_turnover=0.20,
        )
        cache = InMemoryCache()
        registry = StubRegistry()
        service = ModelStabilityService(settings=settings, registry=registry, cache=cache)

        status = service.update_concentration_state(
            {
                "gross_exposure_drift": 0.01,
                "cluster_concentration_drift": 0.03,
                "beta_bucket_concentration_drift": 0.02,
                "cluster_turnover": 0.08,
                "factor_sleeve_budget_turnover": 0.18,
                "max_factor_sleeve_budget_gap_pct": 0.09,
            }
        )

        self.assertFalse(status.degraded)
        self.assertEqual(status.trading_frequency_multiplier, 0.5)
        self.assertAlmostEqual(status.concentration_drift_score, 0.18, places=6)
        history = service.concentration_history()
        self.assertEqual(len(history), 1)
        self.assertAlmostEqual(history[0]["factor_sleeve_budget_turnover"], 0.18, places=6)
        self.assertAlmostEqual(history[0]["max_factor_sleeve_budget_gap_pct"], 0.09, places=6)

    def test_override_active_model_updates_cached_status_immediately(self):
        settings = Settings()
        cache = InMemoryCache()
        registry = StubRegistry()
        service = ModelStabilityService(settings=settings, registry=registry, cache=cache)

        status = service.override_active_model(
            active_model_version="prob-v3",
            fallback_model_version="prob-v2",
            degraded=False,
            retraining_triggered=False,
        )

        self.assertEqual(status.active_model_version, "prob-v3")
        self.assertEqual(status.fallback_model_version, "prob-v2")
        self.assertFalse(status.retraining_triggered)


if __name__ == "__main__":
    unittest.main()
