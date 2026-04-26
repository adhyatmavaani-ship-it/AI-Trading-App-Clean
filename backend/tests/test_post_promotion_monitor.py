import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "post_promotion_monitor.py"
SPEC = importlib.util.spec_from_file_location("post_promotion_monitor", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class PostPromotionMonitorLogicTest(unittest.TestCase):
    def test_evaluate_snapshot_accepts_healthy_metrics(self):
        evaluation = MODULE._evaluate_snapshot(
            {
                "request_total": 20.0,
                "request_error": 0.0,
                "latency_sum": 4.0,
                "latency_count": 20.0,
                "trade_total": 5.0,
                "trade_success": 5.0,
                "gross_exposure": 0.4,
                "max_symbol_exposure": 0.2,
                "max_theme_exposure": 0.25,
                "max_cluster_exposure": 0.25,
                "max_beta_bucket_exposure": 0.3,
                "gross_exposure_drift": 0.03,
                "cluster_concentration_drift": 0.02,
                "beta_bucket_concentration_drift": 0.01,
                "cluster_turnover": 0.20,
                "factor_sleeve_budget_turnover": 0.10,
                "max_factor_sleeve_budget_gap_pct": 0.08,
            },
            {
                "maxErrorRate": 0.05,
                "minTradeSuccessRate": 0.90,
                "maxLatencyMs": 500,
                "maxGrossExposurePct": 0.75,
                "maxSymbolExposurePct": 0.35,
                "maxThemeExposurePct": 0.45,
                "maxClusterExposurePct": 0.45,
                "maxBetaBucketExposurePct": 0.55,
                "maxGrossExposureDriftPct": 0.08,
                "maxClusterConcentrationDriftPct": 0.08,
                "maxBetaBucketConcentrationDriftPct": 0.08,
                "maxClusterTurnover": 0.50,
                "maxFactorSleeveBudgetTurnover": 0.30,
                "maxFactorSleeveBudgetGapPct": 0.18,
                "minimumRequestSamples": 10,
                "minimumTradeSamples": 2,
                "rollbackOnAlert": True,
            },
            (),
        )

        self.assertTrue(evaluation.healthy)
        self.assertEqual(evaluation.reasons, ())
        self.assertAlmostEqual(evaluation.latency_ms, 200.0)

    def test_evaluate_snapshot_flags_active_alerts(self):
        evaluation = MODULE._evaluate_snapshot(
            {
                "request_total": 20.0,
                "request_error": 0.0,
                "latency_sum": 2.0,
                "latency_count": 20.0,
                "trade_total": 0.0,
                "trade_success": 0.0,
                "gross_exposure": 0.8,
                "max_symbol_exposure": 0.4,
                "max_theme_exposure": 0.5,
                "max_cluster_exposure": 0.5,
                "max_beta_bucket_exposure": 0.6,
                "gross_exposure_drift": 0.12,
                "cluster_concentration_drift": 0.11,
                "beta_bucket_concentration_drift": 0.10,
                "cluster_turnover": 0.70,
                "factor_sleeve_budget_turnover": 0.40,
                "max_factor_sleeve_budget_gap_pct": 0.22,
            },
            {
                "maxErrorRate": 0.05,
                "minTradeSuccessRate": 0.90,
                "maxLatencyMs": 500,
                "maxGrossExposurePct": 0.75,
                "maxSymbolExposurePct": 0.35,
                "maxThemeExposurePct": 0.45,
                "maxClusterExposurePct": 0.45,
                "maxBetaBucketExposurePct": 0.55,
                "maxGrossExposureDriftPct": 0.08,
                "maxClusterConcentrationDriftPct": 0.08,
                "maxBetaBucketConcentrationDriftPct": 0.08,
                "maxClusterTurnover": 0.50,
                "maxFactorSleeveBudgetTurnover": 0.30,
                "maxFactorSleeveBudgetGapPct": 0.18,
                "minimumRequestSamples": 10,
                "minimumTradeSamples": 0,
                "rollbackOnAlert": True,
            },
            ("TradingBackendPostPromotionHighErrorRate",),
        )

        self.assertFalse(evaluation.healthy)
        self.assertIn("gross exposure 0.8000 > 0.7500", evaluation.reasons)
        self.assertIn("cluster turnover 0.7000 > 0.5000", evaluation.reasons)
        self.assertIn("sleeve budget gap 0.2200 > 0.1800", evaluation.reasons)
        self.assertIn("alertmanager active alerts: TradingBackendPostPromotionHighErrorRate", evaluation.reasons)

    def test_prometheus_queries_scope_to_stable_rollout(self):
        queries = MODULE._prometheus_queries("trading-prod", "trading-backend", "5m")

        for query in queries.values():
            self.assertIn('namespace="trading-prod"', query)
            self.assertIn('app_kubernetes_io_instance="trading-backend"', query)
            self.assertIn('rollout_track="stable"', query)


if __name__ == "__main__":
    unittest.main()
