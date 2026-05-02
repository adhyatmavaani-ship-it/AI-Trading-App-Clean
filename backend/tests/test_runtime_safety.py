import os
import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings


VALID_GOOGLE_CREDENTIALS_JSON = """{
  "type": "service_account",
  "project_id": "demo-project",
  "private_key_id": "abc123",
  "private_key": "-----BEGIN PRIVATE KEY-----\\nabc\\n-----END PRIVATE KEY-----\\n",
  "client_email": "svc@demo-project.iam.gserviceaccount.com",
  "client_id": "1234567890",
  "token_uri": "https://oauth2.googleapis.com/token"
}"""


class RuntimeSafetyTest(unittest.TestCase):
    def tearDown(self) -> None:
        for key in (
            "ENVIRONMENT",
            "CORS_ALLOWED_ORIGINS",
            "FORCE_EXECUTION_OVERRIDE_ENABLED",
            "AUTH_API_KEYS_JSON",
            "FIRESTORE_PROJECT_ID",
            "GOOGLE_CREDENTIALS_JSON",
            "TRADING_MODE",
            "BINANCE_API_KEY",
            "BINANCE_API_SECRET",
            "TRAINING_BUFFER_PATH",
        ):
            os.environ.pop(key, None)
        get_settings.cache_clear()

    def test_prod_rejects_wildcard_cors(self) -> None:
        os.environ["ENVIRONMENT"] = "prod"
        os.environ["CORS_ALLOWED_ORIGINS"] = '["*"]'
        os.environ["AUTH_API_KEYS_JSON"] = '[{"api_key":"token","user_id":"alice","key_id":"k1"}]'
        get_settings.cache_clear()

        with self.assertRaisesRegex(ValueError, "CORS_ALLOWED_ORIGINS"):
            get_settings()

    def test_prod_requires_auth_configuration(self) -> None:
        os.environ["ENVIRONMENT"] = "prod"
        os.environ["CORS_ALLOWED_ORIGINS"] = '["https://app.example.com"]'
        get_settings.cache_clear()

        with self.assertRaisesRegex(ValueError, "AUTH_API_KEYS_JSON or FIRESTORE_PROJECT_ID"):
            get_settings()

    def test_firestore_requires_google_credentials_json(self) -> None:
        os.environ["ENVIRONMENT"] = "prod"
        os.environ["CORS_ALLOWED_ORIGINS"] = '["https://app.example.com"]'
        os.environ["FIRESTORE_PROJECT_ID"] = "demo-project"
        get_settings.cache_clear()

        with self.assertRaisesRegex(ValueError, "GOOGLE_CREDENTIALS_JSON is required"):
            get_settings()

    def test_firestore_rejects_invalid_google_credentials_json(self) -> None:
        os.environ["ENVIRONMENT"] = "prod"
        os.environ["CORS_ALLOWED_ORIGINS"] = '["https://app.example.com"]'
        os.environ["FIRESTORE_PROJECT_ID"] = "demo-project"
        os.environ["GOOGLE_CREDENTIALS_JSON"] = '{"project_id":"demo-project"'
        get_settings.cache_clear()

        with self.assertRaisesRegex(ValueError, "GOOGLE_CREDENTIALS_JSON must be valid JSON"):
            get_settings()

    def test_firestore_accepts_valid_google_credentials_json(self) -> None:
        os.environ["ENVIRONMENT"] = "prod"
        os.environ["CORS_ALLOWED_ORIGINS"] = '["https://app.example.com"]'
        os.environ["FIRESTORE_PROJECT_ID"] = "demo-project"
        os.environ["GOOGLE_CREDENTIALS_JSON"] = VALID_GOOGLE_CREDENTIALS_JSON
        get_settings.cache_clear()

        settings = get_settings()
        self.assertEqual(settings.firestore_project_id, "demo-project")

    def test_live_mode_requires_exchange_credentials(self) -> None:
        os.environ["ENVIRONMENT"] = "prod"
        os.environ["CORS_ALLOWED_ORIGINS"] = '["https://app.example.com"]'
        os.environ["AUTH_API_KEYS_JSON"] = '[{"api_key":"token","user_id":"alice","key_id":"k1"}]'
        os.environ["TRADING_MODE"] = "live"
        get_settings.cache_clear()

        with self.assertRaisesRegex(ValueError, "TRADING_MODE=live requires"):
            get_settings()

    def test_prod_local_training_buffer_emits_warning(self) -> None:
        os.environ["ENVIRONMENT"] = "prod"
        os.environ["CORS_ALLOWED_ORIGINS"] = '["https://app.example.com"]'
        os.environ["AUTH_API_KEYS_JSON"] = '[{"api_key":"token","user_id":"alice","key_id":"k1"}]'
        os.environ["TRAINING_BUFFER_PATH"] = "artifacts/training_buffer.sqlite3"
        get_settings.cache_clear()

        settings = get_settings()
        self.assertTrue(any("TRAINING_BUFFER_PATH" in warning for warning in settings.runtime_warnings))


if __name__ == "__main__":
    unittest.main()
