import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.append(str(Path(__file__).resolve().parents[1]))

try:
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ModuleNotFoundError:
    FASTAPI_AVAILABLE = False

from app.core.config import get_settings
if FASTAPI_AVAILABLE:
    from app.middleware.auth import AuthMiddleware
from app.services.api_key_auth import ApiKeyAuthService


VALID_GOOGLE_CREDENTIALS_JSON = json.dumps(
    {
        "type": "service_account",
        "project_id": "demo-project",
        "private_key_id": "abc123",
        "private_key": "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----\n",
        "client_email": "svc@demo-project.iam.gserviceaccount.com",
        "client_id": "1234567890",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
)


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi is not installed")
class AuthMiddlewareTest(unittest.TestCase):
    def setUp(self):
        get_settings.cache_clear()

    def tearDown(self):
        get_settings.cache_clear()

    def _build_client(self, auth_api_keys_json: str) -> TestClient:
        settings = get_settings()
        settings.auth_api_keys_json = auth_api_keys_json
        settings.firestore_project_id = ""
        settings.google_credentials_json = ""
        settings.auth_cache_ttl_seconds = 60

        app = FastAPI()
        app.add_middleware(AuthMiddleware)

        @app.get("/secure")
        async def secure(request: Request):
            return {
                "user_id": request.state.user_id,
                "auth_source": request.state.auth_source,
                "api_key_id": request.state.api_key_id,
            }

        @app.get("/v1/health")
        async def health():
            return {"status": "ok"}

        @app.get("/health/live")
        async def health_live():
            return {"status": "alive"}

        return TestClient(app)

    def test_accepts_valid_x_api_key(self):
        client = self._build_client(
            json.dumps(
                [{"api_key": "top-secret-token", "user_id": "alice", "key_id": "key-alice"}]
            )
        )

        response = client.get("/secure", headers={"X-API-Key": "top-secret-token"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user_id"], "alice")
        self.assertEqual(response.json()["auth_source"], "config")
        self.assertEqual(response.json()["api_key_id"], "key-alice")

    def test_accepts_valid_bearer_token(self):
        client = self._build_client(
            json.dumps(
                [{"api_key": "bearer-secret-token", "user_id": "bob", "key_id": "key-bob"}]
            )
        )

        response = client.get("/secure", headers={"Authorization": "Bearer bearer-secret-token"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user_id"], "bob")

    def test_rejects_missing_api_key(self):
        client = self._build_client("[]")

        with patch("app.middleware.auth.logger.warning") as warning_log:
            response = client.get("/secure")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error_code"], "MISSING_API_KEY")
        warning_log.assert_called_once()
        self.assertEqual(
            warning_log.call_args.kwargs["extra"]["context"]["reason"],
            "missing_credentials",
        )

    def test_rejects_unsupported_authorization_scheme(self):
        client = self._build_client("[]")

        with patch("app.middleware.auth.logger.warning") as warning_log:
            response = client.get("/secure", headers={"Authorization": "Basic abc123"})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error_code"], "INVALID_AUTH_SCHEME")
        warning_log.assert_called_once()
        self.assertEqual(
            warning_log.call_args.kwargs["extra"]["context"]["reason"],
            "unsupported_auth_scheme",
        )

    def test_rejects_empty_bearer_token(self):
        client = self._build_client("[]")

        with patch("app.middleware.auth.logger.warning") as warning_log:
            response = client.get("/secure", headers={"Authorization": "Bearer "})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error_code"], "MISSING_API_KEY")
        warning_log.assert_called_once()
        self.assertEqual(
            warning_log.call_args.kwargs["extra"]["context"]["reason"],
            "missing_bearer_token",
        )

    def test_rejects_invalid_api_key(self):
        client = self._build_client(
            json.dumps([{"api_key": "valid-token", "user_id": "alice"}])
        )

        with patch("app.middleware.auth.logger.warning") as warning_log:
            response = client.get("/secure", headers={"X-API-Key": "invalid-token"})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error_code"], "INVALID_API_KEY")
        warning_log.assert_called_once()
        self.assertEqual(warning_log.call_args.args[0], "authentication_failed")
        self.assertEqual(
            warning_log.call_args.kwargs["extra"]["context"]["reason"],
            "invalid_or_expired_api_key",
        )

    def test_rejects_expired_api_key(self):
        client = self._build_client(
            json.dumps(
                [
                    {
                        "api_key": "expired-token",
                        "user_id": "alice",
                        "expires_at": "2025-01-01T00:00:00Z",
                    }
                ]
            )
        )

        with patch("app.middleware.auth.logger.warning") as warning_log:
            response = client.get("/secure", headers={"X-API-Key": "expired-token"})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error_code"], "INVALID_API_KEY")
        warning_log.assert_called_once()
        self.assertEqual(warning_log.call_args.args[0], "authentication_failed")
        self.assertEqual(
            warning_log.call_args.kwargs["extra"]["context"]["reason"],
            "invalid_or_expired_api_key",
        )

    def test_health_path_is_excluded(self):
        client = self._build_client("[]")

        response = client.get("/v1/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_health_probe_path_is_excluded(self):
        client = self._build_client("[]")

        response = client.get("/health/live")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "alive")


class ApiKeyAuthServiceTest(unittest.TestCase):
    def setUp(self):
        get_settings.cache_clear()

    def tearDown(self):
        get_settings.cache_clear()

    def test_issue_api_key_returns_plaintext_and_hash(self):
        settings = get_settings()
        settings.firestore_project_id = ""
        service = ApiKeyAuthService(settings)

        provisioned = service.issue_api_key("alice", key_id="desk-alice")

        self.assertTrue(provisioned.api_key.startswith("atk_"))
        self.assertEqual(provisioned.record["user_id"], "alice")
        self.assertEqual(provisioned.record["key_id"], "desk-alice")
        self.assertEqual(provisioned.record["token_hash"], provisioned.token_hash)
        self.assertEqual(service.authenticate(provisioned.api_key), None)

    def test_issue_api_key_persists_to_firestore_when_enabled(self):
        written: dict[str, dict] = {}

        class FakeDocument:
            def __init__(self, document_id: str):
                self.document_id = document_id

            def set(self, payload: dict, merge: bool = False) -> None:
                written[self.document_id] = {"payload": payload, "merge": merge}

            def get(self):
                payload = written.get(self.document_id, {}).get("payload")
                return SimpleNamespace(exists=payload is not None, to_dict=lambda: payload)

        class FakeCollection:
            def document(self, document_id: str) -> FakeDocument:
                return FakeDocument(document_id)

            def where(self, *_args, **_kwargs):
                return self

            def limit(self, *_args, **_kwargs):
                return self

            def stream(self):
                return iter(())

        class FakeClient:
            def collection(self, _name: str) -> FakeCollection:
                return FakeCollection()

            def collections(self):
                return iter(())

        settings = get_settings()
        settings.firestore_project_id = "demo-project"
        settings.google_credentials_json = VALID_GOOGLE_CREDENTIALS_JSON

        fake_firestore = SimpleNamespace(
            Client=lambda project=None, credentials=None: FakeClient()
        )
        fake_service_account = SimpleNamespace(
            Credentials=SimpleNamespace(
                from_service_account_info=lambda info: SimpleNamespace(info=info)
            )
        )
        with patch("app.services.api_key_auth.firestore", fake_firestore), patch(
            "app.services.api_key_auth.service_account",
            fake_service_account,
        ):
            service = ApiKeyAuthService(settings)
            provisioned = service.issue_api_key("bob", persist_to_firestore=True)
            principal = service.authenticate(provisioned.api_key)

        self.assertIn(provisioned.token_hash, written)
        self.assertTrue(written[provisioned.token_hash]["merge"])
        self.assertIsNotNone(principal)
        self.assertEqual(principal.user_id, "bob")
        self.assertEqual(principal.auth_source, "firestore")

    def test_firestore_authenticates_and_caches_api_key(self):
        token_hash_hits: list[str] = []

        class FakeSnapshot:
            def __init__(self, payload: dict | None):
                self.exists = payload is not None
                self._payload = payload

            def to_dict(self):
                return self._payload

        class FakeDocument:
            def __init__(self, payload: dict):
                self._payload = payload

            def get(self):
                token_hash_hits.append("get")
                return FakeSnapshot(self._payload)

        class FakeCollection:
            def __init__(self, payload: dict):
                self._payload = payload

            def document(self, _document_id: str):
                return FakeDocument(self._payload)

            def where(self, *_args, **_kwargs):
                return self

            def limit(self, *_args, **_kwargs):
                return self

            def stream(self):
                token_hash_hits.append("stream")
                return iter(())

        class FakeClient:
            def __init__(self, payload: dict):
                self._payload = payload

            def collection(self, _name: str):
                return FakeCollection(self._payload)

            def collections(self):
                return iter(())

        settings = get_settings()
        settings.firestore_project_id = "demo-project"
        settings.google_credentials_json = VALID_GOOGLE_CREDENTIALS_JSON
        settings.auth_cache_ttl_seconds = 60

        payload = {
            "user_id": "firestore-user",
            "token_hash": ApiKeyAuthService._hash_api_key("firestore-token"),
            "active": True,
            "revoked": False,
            "key_id": "fire-key",
        }
        fake_firestore = SimpleNamespace(
            Client=lambda project=None, credentials=None: FakeClient(payload)
        )
        fake_service_account = SimpleNamespace(
            Credentials=SimpleNamespace(
                from_service_account_info=lambda info: SimpleNamespace(info=info)
            )
        )
        with patch("app.services.api_key_auth.firestore", fake_firestore), patch(
            "app.services.api_key_auth.service_account",
            fake_service_account,
        ):
            service = ApiKeyAuthService(settings)
            first = service.authenticate("firestore-token")
            second = service.authenticate("firestore-token")

        self.assertIsNotNone(first)
        self.assertEqual(first.user_id, "firestore-user")
        self.assertEqual(second.user_id, "firestore-user")
        self.assertEqual(token_hash_hits.count("get"), 1)

    def test_firestore_credentials_invalid_json_logs_clear_error(self):
        settings = get_settings()
        settings.firestore_project_id = "demo-project"
        settings.google_credentials_json = '{"project_id":"demo-project"'

        with patch("app.services.api_key_auth.logger.error") as error_log:
            with self.assertRaisesRegex(Exception, "GOOGLE_CREDENTIALS_JSON must be valid JSON"):
                ApiKeyAuthService(settings)

        error_log.assert_called()
        self.assertEqual(error_log.call_args.args[0], "firestore_credentials_invalid_json")

    def test_firestore_connection_retries_and_recovers(self):
        attempts: list[str] = []

        class FakeClient:
            def collections(self):
                attempts.append("probe")
                if len(attempts) < 3:
                    raise RuntimeError("temporary firestore outage")
                return iter(())

        settings = get_settings()
        settings.firestore_project_id = "demo-project"
        settings.google_credentials_json = VALID_GOOGLE_CREDENTIALS_JSON

        fake_firestore = SimpleNamespace(
            Client=lambda project=None, credentials=None: FakeClient()
        )
        fake_service_account = SimpleNamespace(
            Credentials=SimpleNamespace(
                from_service_account_info=lambda info: SimpleNamespace(info=info)
            )
        )
        with patch("app.services.api_key_auth.firestore", fake_firestore), patch(
            "app.services.api_key_auth.service_account",
            fake_service_account,
        ), patch("app.services.api_key_auth.time.sleep") as sleep_mock, patch(
            "app.services.api_key_auth.logger.warning"
        ) as warning_log, patch("app.services.api_key_auth.logger.info") as info_log:
            service = ApiKeyAuthService(settings)

        self.assertIsNotNone(service)
        self.assertEqual(len(attempts), 3)
        self.assertEqual(sleep_mock.call_count, 2)
        self.assertEqual(warning_log.call_count, 2)
        info_log.assert_called_once()

    def test_firestore_connection_failure_logs_clear_error(self):
        class FakeClient:
            def collections(self):
                raise RuntimeError("firestore unavailable")

        settings = get_settings()
        settings.firestore_project_id = "demo-project"
        settings.google_credentials_json = VALID_GOOGLE_CREDENTIALS_JSON

        fake_firestore = SimpleNamespace(
            Client=lambda project=None, credentials=None: FakeClient()
        )
        fake_service_account = SimpleNamespace(
            Credentials=SimpleNamespace(
                from_service_account_info=lambda info: SimpleNamespace(info=info)
            )
        )
        with patch("app.services.api_key_auth.firestore", fake_firestore), patch(
            "app.services.api_key_auth.service_account",
            fake_service_account,
        ), patch("app.services.api_key_auth.time.sleep"), patch(
            "app.services.api_key_auth.logger.error"
        ) as error_log:
            with self.assertRaisesRegex(Exception, "Failed to connect to Firestore"):
                ApiKeyAuthService(settings)

        self.assertEqual(error_log.call_args.args[0], "firestore_connection_failed")


if __name__ == "__main__":
    unittest.main()
