import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "canary_rollout.py"
SPEC = importlib.util.spec_from_file_location("canary_rollout", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class CanaryRolloutLogicTest(unittest.TestCase):
    def test_parse_metrics_extracts_error_latency_and_trade_success(self):
        snapshot = MODULE._parse_metrics(
            """
            # HELP api_requests_total HTTP requests
            api_requests_total{method="GET",endpoint="/",status_code="200"} 12
            api_requests_total{method="POST",endpoint="/v1/trading/execute",status_code="500"} 1
            api_request_latency_seconds_sum{endpoint="/"} 2.4
            api_request_latency_seconds_count{endpoint="/"} 6
            trading_executions_total{side="BUY",status="SUCCESS"} 4
            trading_executions_total{side="SELL",status="FAILURE"} 1
            portfolio_gross_exposure_pct 0.42
            portfolio_max_symbol_exposure_pct 0.21
            portfolio_max_theme_exposure_pct 0.25
            portfolio_max_cluster_exposure_pct 0.22
            portfolio_max_beta_bucket_exposure_pct 0.30
            portfolio_gross_exposure_drift_pct 0.04
            portfolio_cluster_concentration_drift_pct 0.03
            portfolio_beta_bucket_concentration_drift_pct 0.02
            portfolio_cluster_turnover 0.20
            portfolio_factor_sleeve_budget_turnover 0.12
            portfolio_max_factor_sleeve_budget_gap_pct 0.09
            """
        )

        self.assertEqual(snapshot.total_requests, 13.0)
        self.assertEqual(snapshot.error_requests, 1.0)
        self.assertEqual(snapshot.latency_sum_seconds, 2.4)
        self.assertEqual(snapshot.latency_count, 6.0)
        self.assertEqual(snapshot.trade_total, 5.0)
        self.assertEqual(snapshot.trade_success, 4.0)
        self.assertEqual(snapshot.portfolio_gross_exposure_pct, 0.42)
        self.assertEqual(snapshot.portfolio_max_cluster_exposure_pct, 0.22)
        self.assertEqual(snapshot.portfolio_cluster_turnover, 0.20)
        self.assertEqual(snapshot.portfolio_factor_sleeve_budget_turnover, 0.12)
        self.assertEqual(snapshot.portfolio_max_factor_sleeve_budget_gap_pct, 0.09)

    def test_evaluate_canary_flags_unhealthy_metrics(self):
        delta = MODULE.MetricSnapshot(
            total_requests=10.0,
            error_requests=2.0,
            latency_sum_seconds=8.0,
            latency_count=10.0,
            trade_total=3.0,
            trade_success=2.0,
            portfolio_gross_exposure_pct=0.8,
            portfolio_max_symbol_exposure_pct=0.4,
            portfolio_max_theme_exposure_pct=0.5,
            portfolio_max_cluster_exposure_pct=0.5,
            portfolio_max_beta_bucket_exposure_pct=0.6,
            portfolio_gross_exposure_drift_pct=0.12,
            portfolio_cluster_concentration_drift_pct=0.11,
            portfolio_beta_bucket_concentration_drift_pct=0.10,
            portfolio_cluster_turnover=0.70,
            portfolio_factor_sleeve_budget_turnover=0.40,
            portfolio_max_factor_sleeve_budget_gap_pct=0.22,
        )

        evaluation = MODULE._evaluate_canary(
            delta,
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
                "minimumRequestSamples": 5,
                "minimumTradeSamples": 2,
            },
        )

        self.assertFalse(evaluation.healthy)
        self.assertIn("error rate 0.2000 > 0.0500", evaluation.reasons)
        self.assertIn("latency 800.00ms > 500.00ms", evaluation.reasons)
        self.assertIn("trade success rate 0.6667 < 0.9000", evaluation.reasons)
        self.assertIn("gross exposure 0.8000 > 0.7500", evaluation.reasons)
        self.assertIn("gross exposure drift 0.1200 > 0.0800", evaluation.reasons)
        self.assertIn("sleeve budget turnover 0.4000 > 0.3000", evaluation.reasons)

    def test_evaluate_canary_accepts_healthy_metrics(self):
        delta = MODULE.MetricSnapshot(
            total_requests=12.0,
            error_requests=0.0,
            latency_sum_seconds=2.4,
            latency_count=12.0,
            trade_total=0.0,
            trade_success=0.0,
            portfolio_gross_exposure_pct=0.4,
            portfolio_max_symbol_exposure_pct=0.2,
            portfolio_max_theme_exposure_pct=0.2,
            portfolio_max_cluster_exposure_pct=0.2,
            portfolio_max_beta_bucket_exposure_pct=0.2,
            portfolio_gross_exposure_drift_pct=0.03,
            portfolio_cluster_concentration_drift_pct=0.02,
            portfolio_beta_bucket_concentration_drift_pct=0.01,
            portfolio_cluster_turnover=0.20,
            portfolio_factor_sleeve_budget_turnover=0.10,
            portfolio_max_factor_sleeve_budget_gap_pct=0.08,
        )

        evaluation = MODULE._evaluate_canary(
            delta,
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
                "minimumRequestSamples": 6,
                "minimumTradeSamples": 0,
            },
        )

        self.assertTrue(evaluation.healthy)
        self.assertEqual(evaluation.reasons, ())
        self.assertAlmostEqual(evaluation.avg_latency_ms, 200.0)


if __name__ == "__main__":
    unittest.main()
