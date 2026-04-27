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
    from app.api.routes import frontend
    from app.middleware.auth import AuthMiddleware
    from app.services.container import get_container


class StubAnalyticsService:
    def active_trades(self, user_id: str):
        return [{"trade_id": "t1", "symbol": "BTCUSDT"}]

    def trade_history(self, user_id: str, limit: int = 100):
        return [{"trade_id": "t1", "profit_pct": 1.25}]

    def summary(self, user_id: str):
        return {"user_id": user_id, "win_rate": 0.6, "expectancy": 0.4, "best_symbols": ["BTCUSDT"], "best_regime": "TRENDING", "worst_regime": "RANGING", "regime_win_rates": {"TRENDING": 0.64, "RANGING": 0.42}, "worst_exit_reasons": ["volume_reversal"], "most_profitable_setup": "structure + momentum", "false_signal_rate": 0.25, "capital_utilization": 0.42, "risk_exposure": 0.03, "correlation_risk": 0.6, "regime_distribution": {"TRENDING": 0.5, "RANGING": 0.3, "HIGH_VOL": 0.2}}

    def performance(self, user_id: str):
        return {"summary": {"user_id": user_id}, "weights": {"structure": 0.4, "momentum": 0.3, "volume": 0.3}}


class StubUserExperienceEngine:
    def latest(self):
        return {"status": "scanning", "bot_state": "SCANNING", "message": "BTC checked -> weak volume, skipped", "intent": "Watching BTC for stronger volume", "readiness": 41}

    def history(self, limit: int = 25):
        return [
            {"status": "scanning", "message": "Scanning BTC..."},
            {"status": "almost_trade", "message": "ETH almost triggered trade"},
        ][:limit]

    def readiness(self, limit: int = 8):
        return [
            {"symbol": "ETHUSDT", "readiness": 68, "status": "almost_trade"},
            {"symbol": "BTCUSDT", "readiness": 41, "status": "scanning"},
        ][:limit]


class StubContainer:
    def __init__(self):
        self.analytics_service = StubAnalyticsService()
        self.user_experience_engine = StubUserExperienceEngine()


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi is not installed")
class FrontendAnalyticsRoutesTest(unittest.TestCase):
    def setUp(self):
        from app.core.config import get_settings

        get_settings.cache_clear()
        settings = get_settings()
        settings.auth_api_keys_json = '[{"api_key":"route-token","user_id":"alice","key_id":"alice-key"}]'
        settings.firestore_project_id = ""
        settings.auth_cache_ttl_seconds = 60

        app = FastAPI()
        app.add_middleware(AuthMiddleware)
        app.include_router(frontend.router, prefix="/v1")
        app.dependency_overrides[get_container] = lambda: StubContainer()
        self.app = app
        self.client = TestClient(app)

    def tearDown(self):
        self.app.dependency_overrides.clear()
        from app.core.config import get_settings

        get_settings.cache_clear()

    def test_active_trades_endpoint(self):
        response = self.client.get("/v1/trades/active?user_id=alice", headers={"X-API-Key": "route-token"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)

    def test_trade_history_endpoint(self):
        response = self.client.get("/v1/trades/history?user_id=alice", headers={"X-API-Key": "route-token"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)

    def test_analytics_summary_endpoint(self):
        response = self.client.get("/v1/analytics/summary?user_id=alice", headers={"X-API-Key": "route-token"})
        self.assertEqual(response.status_code, 200)
        self.assertAlmostEqual(response.json()["win_rate"], 0.6, places=6)
        self.assertEqual(response.json()["best_symbols"][0], "BTCUSDT")

    def test_analytics_performance_endpoint(self):
        response = self.client.get("/v1/analytics/performance?user_id=alice", headers={"X-API-Key": "route-token"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("weights", response.json())

    def test_activity_live_endpoint(self):
        response = self.client.get("/v1/activity/live", headers={"X-API-Key": "route-token"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["bot_state"], "SCANNING")

    def test_activity_history_endpoint(self):
        response = self.client.get("/v1/activity/history", headers={"X-API-Key": "route-token"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 2)

    def test_activity_readiness_endpoint(self):
        response = self.client.get("/v1/activity/readiness", headers={"X-API-Key": "route-token"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["symbol"], "ETHUSDT")


if __name__ == "__main__":
    unittest.main()
