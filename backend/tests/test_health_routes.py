import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ModuleNotFoundError:
    FASTAPI_AVAILABLE = False

if FASTAPI_AVAILABLE:
    from app.api.routes import health
    from app.middleware.auth import AuthMiddleware
    from app.services.container import get_container


class StubCacheClient:
    def ping(self) -> bool:
        return True


class StubCache:
    def __init__(self):
        self.client = StubCacheClient()


class HealthyFirestoreClient:
    def collections(self):
        return iter(())


class BrokenFirestoreClient:
    def collections(self):
        raise RuntimeError("firestore probe failed")


class StubFirestore:
    def __init__(self, client=None):
        self.client = client


class StubMarketData:
    latest_stream_price = {}

    async def fetch_latest_price(self, symbol: str) -> float:
        return 0.0


class StubContainer:
    def __init__(self, firestore_client=None):
        self.cache = StubCache()
        self.firestore = StubFirestore(firestore_client)
        self.market_data = StubMarketData()


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi is not installed")
class HealthRoutesTest(unittest.TestCase):
    def _build_client(self, firestore_client=None) -> TestClient:
        app = FastAPI()
        app.add_middleware(AuthMiddleware)
        app.include_router(health.router)
        app.dependency_overrides[get_container] = lambda: StubContainer(firestore_client)
        self.addCleanup(app.dependency_overrides.clear)
        return TestClient(app)

    def test_health_returns_ok_with_readiness_details(self):
        client = self._build_client(HealthyFirestoreClient())

        response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["firestore"], "ready")
        self.assertTrue(payload["readiness"]["ready"])
        self.assertEqual(payload["readiness"]["checks"]["redis"], "ready")
        self.assertEqual(payload["readiness"]["checks"]["market_data"], "ready")

    def test_health_returns_503_when_firestore_probe_fails(self):
        client = self._build_client(BrokenFirestoreClient())

        response = client.get("/health")

        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertEqual(payload["status"], "error")
        self.assertFalse(payload["readiness"]["ready"])
        self.assertTrue(payload["firestore"].startswith("error:"))


if __name__ == "__main__":
    unittest.main()
