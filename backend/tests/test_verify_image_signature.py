import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "verify_image_signature.py"


class VerifyImageSignatureScriptTest(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT_PATH), *args],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_verify_succeeds_with_fake_cosign_success(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cosign_script = Path(temp_dir) / "fake_cosign.py"
            cosign_script.write_text(
                textwrap.dedent(
                    """
                    import json
                    import sys
                    print(json.dumps([{"critical": {"identity": {"docker-reference": sys.argv[2]}}}]))
                    """
                ),
                encoding="utf-8",
            )
            result = self._run(
                "--repository",
                "gcr.io/example/trading-backend",
                "--digest",
                "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "--identity",
                "https://github.com/example/repo/.github/workflows/sign.yml@refs/heads/main",
                "--oidc-issuer",
                "https://token.actions.githubusercontent.com",
                "--cosign-bin",
                f'"{sys.executable}" "{cosign_script}"',
            )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("Verified signature", result.stdout)

    def test_verify_fails_when_cosign_returns_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cosign_script = Path(temp_dir) / "fake_cosign_fail.py"
            cosign_script.write_text(
                textwrap.dedent(
                    """
                    import sys
                    print("no signatures found", file=sys.stderr)
                    raise SystemExit(1)
                    """
                ),
                encoding="utf-8",
            )
            result = self._run(
                "--repository",
                "gcr.io/example/trading-backend",
                "--digest",
                "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "--identity",
                "https://github.com/example/repo/.github/workflows/sign.yml@refs/heads/main",
                "--oidc-issuer",
                "https://token.actions.githubusercontent.com",
                "--cosign-bin",
                f'"{sys.executable}" "{cosign_script}"',
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Signature verification failed", result.stderr)

    def test_verify_fails_for_invalid_digest_shape(self):
        result = self._run(
            "--repository",
            "gcr.io/example/trading-backend",
            "--digest",
            "bad-digest",
            "--identity",
            "https://github.com/example/repo/.github/workflows/sign.yml@refs/heads/main",
            "--oidc-issuer",
            "https://token.actions.githubusercontent.com",
            "--cosign-bin",
            sys.executable,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("sha256", result.stderr)


if __name__ == "__main__":
    unittest.main()
