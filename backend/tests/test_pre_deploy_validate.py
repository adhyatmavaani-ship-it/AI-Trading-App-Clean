import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "pre_deploy_validate.py"


class PreDeployValidateScriptTest(unittest.TestCase):
    def _run(self, manifest_path: Path, values_path: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--manifest", str(manifest_path), "--values-file", str(values_path)],
            check=False,
            capture_output=True,
            text=True,
        )

    def _write_manifest(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "environment": "staging",
                    "namespace": "trading-staging",
                    "release_name": "trading-backend",
                    "deployment": "trading-backend",
                    "service": "trading-backend",
                    "chart_path": "infrastructure/helm",
                    "values_file": "values.yaml",
                    "context": "staging-cluster",
                    "ai_model_version": "v1",
                    "strategy": {
                        "default": "ensemble",
                        "enabled": ["ensemble", "hybrid_crypto", "ema_crossover", "rsi", "breakout"],
                    },
                    "image": {
                        "repository": "gcr.io/example/trading-backend",
                        "digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    },
                    "signature": {
                        "identity": "https://github.com/example/repo/.github/workflows/sign-release-image.yml@refs/heads/main",
                        "oidc_issuer": "https://token.actions.githubusercontent.com",
                    },
                }
            ),
            encoding="utf-8",
        )

    def _write_values(
        self,
        path: Path,
        *,
        base_risk: str = "0.02",
        model_version: str = "v1",
        include_trade_size: bool = True,
        include_canary: bool = True,
        ingress_enabled: bool = True,
        canary_weight: str = "10",
    ) -> None:
        lines = [
            "config:",
            f'  BASE_RISK_PER_TRADE: "{base_risk}"',
            '  DAILY_LOSS_LIMIT: "0.05"',
            '  GLOBAL_MAX_CAPITAL_LOSS: "0.10"',
            '  ROLLING_DRAWDOWN_LIMIT: "0.06"',
            '  PAUSE_DRAWDOWN_LIMIT: "0.10"',
        ]
        if include_trade_size:
            lines.append('  MAX_COIN_EXPOSURE_PCT: "0.20"')
        lines.extend(
            [
                f'  AI_MODEL_VERSION: "{model_version}"',
                '  DEFAULT_STRATEGY: "ensemble"',
                '  ENABLED_STRATEGIES: "ensemble,hybrid_crypto,ema_crossover,rsi,breakout"',
            ]
        )
        if include_canary:
            lines.extend(
                [
                    "canary:",
                    f'  weight: {canary_weight}',
                    "  analysis:",
                    '    durationSeconds: 120',
                    '    intervalSeconds: 10',
                    '    maxErrorRate: 0.05',
                    '    minTradeSuccessRate: 0.90',
                    '    maxLatencyMs: 500',
                    '    maxGrossExposurePct: 0.75',
                    '    maxSymbolExposurePct: 0.35',
                    '    maxThemeExposurePct: 0.45',
                    '    maxClusterExposurePct: 0.45',
                    '    maxBetaBucketExposurePct: 0.55',
                    '    maxGrossExposureDriftPct: 0.08',
                    '    maxClusterConcentrationDriftPct: 0.08',
                    '    maxBetaBucketConcentrationDriftPct: 0.08',
                    '    maxClusterTurnover: 0.50',
                    '    maxFactorSleeveBudgetTurnover: 0.30',
                    '    maxFactorSleeveBudgetGapPct: 0.18',
                    '    minimumRequestSamples: 6',
                    '    minimumTradeSamples: 0',
                    "ingress:",
                    f"  enabled: {'true' if ingress_enabled else 'false'}",
                ]
            )
        lines.extend(
            [
                "rolloutMonitoring:",
                "  enabled: true",
                "  prometheus:",
                '    namespace: "monitoring"',
                '    serviceName: "kube-prometheus-stack-prometheus"',
                "    port: 9090",
                "  alertmanager:",
                '    namespace: "monitoring"',
                '    serviceName: "kube-prometheus-stack-alertmanager"',
                "    port: 9093",
                "  analysis:",
                "    durationSeconds: 180",
                "    intervalSeconds: 30",
                '    lookbackWindow: "5m"',
                "    maxErrorRate: 0.05",
                "    minTradeSuccessRate: 0.90",
                "    maxLatencyMs: 500",
                "    maxGrossExposurePct: 0.75",
                "    maxSymbolExposurePct: 0.35",
                "    maxThemeExposurePct: 0.45",
                "    maxClusterExposurePct: 0.45",
                "    maxBetaBucketExposurePct: 0.55",
                "    maxGrossExposureDriftPct: 0.08",
                "    maxClusterConcentrationDriftPct: 0.08",
                "    maxBetaBucketConcentrationDriftPct: 0.08",
                "    maxClusterTurnover: 0.50",
                "    maxFactorSleeveBudgetTurnover: 0.30",
                "    maxFactorSleeveBudgetGapPct: 0.18",
                "    minimumRequestSamples: 10",
                "    minimumTradeSamples: 0",
                "    rollbackOnAlert: true",
                "    alertNames:",
                '    - "TradingBackendPostPromotionHighErrorRate"',
                '    - "TradingBackendPostPromotionHighConcentration"',
            ]
        )
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_validation_passes_for_safe_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            manifest = temp_path / "manifest.json"
            values = temp_path / "values.yaml"
            self._write_manifest(manifest)
            self._write_values(values)

            result = self._run(manifest, values)

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("Pre-deploy validation passed", result.stdout)

    def test_validation_fails_for_unsafe_risk_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            manifest = temp_path / "manifest.json"
            values = temp_path / "values.yaml"
            self._write_manifest(manifest)
            self._write_values(values, base_risk="0.03")

            result = self._run(manifest, values)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsafe BASE_RISK_PER_TRADE", result.stderr)

    def test_validation_fails_when_required_parameter_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            manifest = temp_path / "manifest.json"
            values = temp_path / "values.yaml"
            self._write_manifest(manifest)
            self._write_values(values, include_trade_size=False)

            result = self._run(manifest, values)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing required config keys", result.stderr)

    def test_validation_fails_for_invalid_canary_weight(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            manifest = temp_path / "manifest.json"
            values = temp_path / "values.yaml"
            self._write_manifest(manifest)
            self._write_values(values, canary_weight="20")

            result = self._run(manifest, values)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("canary.weight must be 10", result.stderr)

    def test_validation_fails_when_canary_routing_has_no_ingress(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            manifest = temp_path / "manifest.json"
            values = temp_path / "values.yaml"
            self._write_manifest(manifest)
            self._write_values(values, ingress_enabled=False)

            result = self._run(manifest, values)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ingress.enabled must be true", result.stderr)


if __name__ == "__main__":
    unittest.main()
