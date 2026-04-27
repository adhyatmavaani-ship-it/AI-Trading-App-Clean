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
    from app.api.routes import backtest_jobs
    from app.middleware.auth import AuthMiddleware
    from app.services.container import get_container


class StubBacktestJobService:
    def enqueue(self, *, request, user_id: str):
        return {
            "job_id": "job-1",
            "user_id": user_id,
            "status": "QUEUED",
            "progress_pct": 0.0,
            "current_stage": "queued",
            "trades_found": 0,
            "net_profit": 0.0,
            "heartbeat_at": "2026-04-27T00:00:00+00:00",
            "created_at": "2026-04-27T00:00:00+00:00",
            "started_at": None,
            "completed_at": None,
            "error": None,
            "logs": [],
            "result": None,
        }

    def status(self, job_id: str):
        if job_id != "job-1":
            raise ValueError("Unknown backtest job: job-missing")
        return {
            "job_id": "job-1",
            "user_id": "alice",
            "status": "COMPLETED",
            "progress_pct": 100.0,
            "current_stage": "completed",
            "trades_found": 3,
            "net_profit": 42.0,
            "heartbeat_at": "2026-04-27T00:01:00+00:00",
            "created_at": "2026-04-27T00:00:00+00:00",
            "started_at": "2026-04-27T00:00:05+00:00",
            "completed_at": "2026-04-27T00:01:00+00:00",
            "error": None,
            "logs": [],
            "result": {
                "summary": {
                    "symbol": "BTCUSDT",
                    "timeframe": "5m",
                    "strategy": "ensemble",
                    "days": 7,
                    "starting_balance": 10000.0,
                    "final_equity": 10042.0,
                    "total_profit": 42.0,
                    "roi_pct": 0.42,
                    "win_rate": 0.66,
                    "max_drawdown": 0.05,
                    "profit_factor": 1.8,
                    "total_trades": 3,
                },
                "equity_curve": [],
                "trades": [],
            },
        }

    def enqueue_compare(self, *, request, user_id: str):
        return {
            "job_id": "job-compare-1",
            "user_id": user_id,
            "status": "QUEUED",
            "progress_pct": 0.0,
            "current_stage": "queued",
            "trades_found": 0,
            "net_profit": 0.0,
            "heartbeat_at": "2026-04-27T00:00:00+00:00",
            "created_at": "2026-04-27T00:00:00+00:00",
            "started_at": None,
            "completed_at": None,
            "error": None,
            "logs": [],
            "result": None,
            "comparison_profiles": [],
        }

    def export_csv(self, job_id: str):
        return ("backtest_job-1.csv", 'risk_profile,side\n"low","BUY"')


class StubContainer:
    def __init__(self):
        self.backtest_job_service = StubBacktestJobService()


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi is not installed")
class BacktestJobRoutesTest(unittest.TestCase):
    def setUp(self):
        from app.core.config import get_settings

        get_settings.cache_clear()
        settings = get_settings()
        settings.auth_api_keys_json = '[{"api_key":"route-token","user_id":"alice","key_id":"alice-key"}]'
        settings.firestore_project_id = ""
        settings.auth_cache_ttl_seconds = 60

        app = FastAPI()
        app.add_middleware(AuthMiddleware)
        app.include_router(backtest_jobs.router, prefix="/v1")
        app.dependency_overrides[get_container] = lambda: StubContainer()
        self.app = app
        self.client = TestClient(app)

    def tearDown(self):
        self.app.dependency_overrides.clear()
        from app.core.config import get_settings

        get_settings.cache_clear()

    def test_run_backtest_job_returns_job_id(self):
        response = self.client.post(
            "/v1/backtest/run",
            headers={"X-API-Key": "route-token"},
            json={"symbol": "BTCUSDT", "days": 7},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["job_id"], "job-1")

    def test_backtest_job_status_returns_result(self):
        response = self.client.get(
            "/v1/backtest/status/job-1",
            headers={"X-API-Key": "route-token"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "COMPLETED")
        self.assertEqual(response.json()["result"]["summary"]["symbol"], "BTCUSDT")

    def test_compare_backtest_job_returns_job_id(self):
        response = self.client.post(
            "/v1/backtest/compare",
            headers={"X-API-Key": "route-token"},
            json={"symbol": "BTCUSDT", "days": 7, "profiles": ["low", "high"]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["job_id"], "job-compare-1")

    def test_export_backtest_job_returns_csv(self):
        response = self.client.get(
            "/v1/backtest/export/job-1",
            headers={"X-API-Key": "route-token"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "text/csv; charset=utf-8")
        self.assertIn('risk_profile,side', response.text)


if __name__ == "__main__":
    unittest.main()
