import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ModuleNotFoundError:
    FASTAPI_AVAILABLE = False

if FASTAPI_AVAILABLE:
    from app.api.routes import public
    from app.middleware.auth import AuthMiddleware
    from app.services.container import get_container


class StubCache:
    def __init__(self):
        self.store = {}

    def get_json(self, key):
        return self.store.get(key)

    def set_json(self, key, value, ttl):
        self.store[key] = value


class StubFirestore:
    def __init__(self):
        self.performance_calls = 0
        self.trade_calls = 0
        self.daily_calls = 0

    def load_public_performance_summary(self, trade_limit=1000):
        self.performance_calls += 1
        return {
            "win_rate": 0.63,
            "total_pnl_pct": 18.4,
            "total_trades": 142,
            "last_updated": datetime(2026, 4, 26, tzinfo=timezone.utc),
        }

    def list_closed_trades(self, limit=20):
        self.trade_calls += 1
        return [
            {
                "symbol": "BTCUSDT",
                "side": "BUY",
                "entry": 100.0,
                "exit": 108.0,
                "status": "CLOSED",
                "user_id": "alice",
            },
            {
                "symbol": "ETHUSDT",
                "side": "SELL",
                "entry": 200.0,
                "exit": 206.0,
                "status": "CLOSED",
                "user_id": "bob",
            },
        ][:limit]

    def load_public_daily_results(self, limit=90):
        self.daily_calls += 1
        return [
            {"date": "2026-04-24", "pnl_pct": 1.2},
            {"date": "2026-04-25", "pnl_pct": -0.4},
        ][:limit]


class StubContainer:
    def __init__(self):
        self.cache = StubCache()
        self.firestore = StubFirestore()


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi is not installed")
class PublicRoutesTest(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.add_middleware(AuthMiddleware)
        app.include_router(public.router, prefix="/v1")
        self.container = StubContainer()
        app.dependency_overrides[get_container] = lambda: self.container
        self.app = app
        self.client = TestClient(app)

    def tearDown(self):
        self.app.dependency_overrides.clear()

    def test_public_performance_is_accessible_without_auth_and_cached(self):
        first = self.client.get("/v1/public/performance")
        second = self.client.get("/v1/public/performance")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["win_rate"], 0.63)
        self.assertEqual(self.container.firestore.performance_calls, 1)

    def test_public_trades_are_anonymized(self):
        response = self.client.get("/v1/public/trades?limit=2")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 2)
        self.assertNotIn("user_id", payload["items"][0])
        self.assertEqual(payload["items"][0]["status"], "WIN")
        self.assertEqual(payload["items"][1]["status"], "LOSS")

    def test_public_daily_returns_series_without_auth(self):
        response = self.client.get("/v1/public/daily")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 2)
        self.assertEqual(payload["items"][0]["date"], "2026-04-24")


if __name__ == "__main__":
    unittest.main()
