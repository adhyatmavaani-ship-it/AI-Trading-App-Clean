import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "release_manifest.py"


class ReleaseManifestScriptTest(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT_PATH), *args],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_resolve_accepts_valid_digest_manifest(self):
        result = self._run("resolve", "--manifest", str(REPO_ROOT / "deploy" / "releases" / "staging.json"))

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["image"]["repository"], "gcr.io/MY-PROJECT-ID/trading-backend")
        self.assertTrue(payload["image"]["digest"].startswith("sha256:"))

    def test_resolve_rejects_manifest_without_sha256_digest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "invalid.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "environment": "staging",
                        "namespace": "trading-staging",
                        "release_name": "trading-backend",
                        "deployment": "trading-backend",
                        "service": "trading-backend",
                        "chart_path": "infrastructure/helm",
                        "values_file": "infrastructure/helm/values-staging.yaml",
                        "ai_model_version": "v1",
                        "strategy": {
                            "default": "ensemble",
                            "enabled": ["ensemble", "hybrid_crypto", "ema_crossover", "rsi", "breakout"],
                        },
                        "image": {
                            "repository": "gcr.io/example/trading-backend",
                            "digest": "not-a-digest",
                        },
                        "signature": {
                            "identity": "https://github.com/example/repo/.github/workflows/sign-release-image.yml@refs/heads/main",
                            "oidc_issuer": "https://token.actions.githubusercontent.com",
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = self._run("resolve", "--manifest", str(manifest_path))

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("image.digest must start with sha256:", result.stderr)

    def test_promote_copies_digest_to_target_manifest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.json"
            target = Path(temp_dir) / "target.json"
            source.write_text(
                json.dumps(
                    {
                        "environment": "staging",
                        "namespace": "trading-staging",
                        "release_name": "trading-backend",
                        "deployment": "trading-backend",
                        "service": "trading-backend",
                        "chart_path": "infrastructure/helm",
                        "values_file": "infrastructure/helm/values-staging.yaml",
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
            target.write_text(
                json.dumps(
                    {
                        "environment": "production",
                        "namespace": "trading-prod",
                        "release_name": "trading-backend",
                        "deployment": "trading-backend",
                        "service": "trading-backend",
                        "chart_path": "infrastructure/helm",
                        "values_file": "infrastructure/helm/values-prod.yaml",
                        "ai_model_version": "v1",
                        "strategy": {
                            "default": "ensemble",
                            "enabled": ["ensemble", "hybrid_crypto", "ema_crossover", "rsi", "breakout"],
                        },
                        "image": {
                            "repository": "gcr.io/example/trading-backend",
                            "digest": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                        },
                        "signature": {
                            "identity": "https://github.com/example/repo/.github/workflows/sign-release-image.yml@refs/heads/main",
                            "oidc_issuer": "https://token.actions.githubusercontent.com",
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = self._run("promote", "--source", str(source), "--target", str(target))
            updated = json.loads(target.read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(
            updated["image"]["digest"],
            "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )
        self.assertIn("promotion", updated)


if __name__ == "__main__":
    unittest.main()
