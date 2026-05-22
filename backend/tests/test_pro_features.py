import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

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
    from app.services.ai_copilot import AICopilotService
    from app.services.automated_journal import AutomatedJournalService
    from app.services.container import get_container
    from app.services.pro_scanner import ProScannerService
    from app.services.strategy_marketplace import StrategyMarketplaceService


class StubCache:
    def __init__(self):
        self.store = {}

    def get_json(self, key):
        return self.store.get(key)

    def set_json(self, key, value, ttl):
        self.store[key] = value


class StubMarketData:
    async def fetch_multi_timeframe_ohlcv(self, symbol: str, intervals=("1h",)):
        frames = {}
        for interval in intervals:
            rows = []
            for index in range(80):
                close = 100.0 + index * 0.35
                rows.append(
                    {
                        "open_time": 1714212000000 + index * 300000,
                        "close_time": 1714212300000 + index * 300000,
                        "open": close - 0.2,
                        "high": close + 1.1,
                        "low": close - 1.0,
                        "close": close,
                        "volume": 200.0 if index == 79 else 80.0 + index,
                    }
                )
            frames[interval] = pd.DataFrame(rows)
        return frames


class StubContainer:
    def __init__(self):
        cache = StubCache()
        market_data = StubMarketData()
        self.settings = SimpleNamespace()
        self.cache = cache
        self.ai_copilot_service = AICopilotService(market_data=market_data)
        self.pro_scanner_service = ProScannerService(market_data=market_data)
        self.strategy_marketplace_service = StrategyMarketplaceService(cache=cache)
        self.automated_journal_service = AutomatedJournalService(cache=cache)


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi is not installed")
class ProFeaturesRoutesTest(unittest.TestCase):
    def setUp(self):
        from app.core.config import get_settings

        get_settings.cache_clear()
        settings = get_settings()
        settings.auth_api_keys_json = '[{"api_key":"pro-token","user_id":"alice","key_id":"alice-key"}]'
        settings.firestore_project_id = ""
        settings.auth_cache_ttl_seconds = 60

        app = FastAPI()
        app.add_middleware(AuthMiddleware)
        app.include_router(frontend.router, prefix="/v1")
        self.container = StubContainer()
        app.dependency_overrides[get_container] = lambda: self.container
        self.app = app
        self.client = TestClient(app)

    def tearDown(self):
        self.app.dependency_overrides.clear()
        from app.core.config import get_settings

        get_settings.cache_clear()

    def test_copilot_answers_with_live_market_facts(self):
        response = self.client.post(
            "/v1/pro/copilot/chat",
            json={
                "symbol": "BTCUSDT",
                "timeframe": "4h",
                "prompt": "What is the support level for BTC and any MACD crossover on 4H?",
            },
            headers={"X-API-Key": "pro-token"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["symbol"], "BTCUSDT")
        self.assertEqual(payload["timeframe"], "4h")
        self.assertIn("support", payload["facts"])
        self.assertIn("macd_crossover", payload["facts"])

    def test_custom_scanner_returns_matches_and_alert_event(self):
        response = self.client.post(
            "/v1/pro/scanner/run",
            json={
                "symbols": ["BTCUSDT", "ETHUSDT"],
                "timeframe": "1h",
                "criteria": [
                    {"field": "rsi", "operator": "below", "value": 101},
                    {"field": "volume_ratio", "operator": "above", "value": 0.5},
                ],
            },
            headers={"X-API-Key": "pro-token"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(payload["match_count"], 1)
        self.assertTrue(payload["notification_event"]["enabled"])

    def test_marketplace_rejects_screenshots_and_auto_weights_verified_strategy(self):
        rejected = self.client.post(
            "/v1/pro/marketplace/strategies",
            json={
                "name": "Screenshot Alpha",
                "style": "breakout",
                "evidence_type": "screenshot",
                "metrics": {"trade_count": 12, "win_rate": 0.7, "profit_factor": 2.0},
            },
            headers={"X-API-Key": "pro-token"},
        )
        self.assertEqual(rejected.status_code, 400)

        accepted = self.client.post(
            "/v1/pro/marketplace/strategies",
            json={
                "name": "Ledger Breakout",
                "style": "breakout",
                "evidence_type": "paper_ledger",
                "metrics": {"trade_count": 20, "win_rate": 0.62, "profit_factor": 1.8, "max_drawdown": 0.05},
            },
            headers={"X-API-Key": "pro-token"},
        )
        self.assertEqual(accepted.status_code, 200)
        self.assertTrue(accepted.json()["verified"])

        weights = self.client.get(
            "/v1/pro/marketplace/weights?regime=TRENDING",
            headers={"X-API-Key": "pro-token"},
        )
        self.assertEqual(weights.status_code, 200)
        self.assertEqual(weights.json()["weights"][0]["style"], "trend_following")

    def test_journal_report_generates_snapshot_and_psychology_tags(self):
        response = self.client.post(
            "/v1/pro/journal/report",
            json={
                "trade": {
                    "symbol": "BTCUSDT",
                    "side": "BUY",
                    "entry_price": 100.0,
                    "exit_price": 95.0,
                    "pnl": -500.0,
                    "entry_timestamp": "2026-05-23T08:00:00+00:00",
                    "exit_timestamp": "2026-05-23T11:00:00+00:00",
                    "reason": "AI said WAIT because RSI was overbought",
                }
            },
            headers={"X-API-Key": "pro-token"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["result"], "LOSS")
        self.assertIn("late_loser_exit", payload["psychology_tags"])
        self.assertIn("fomo_entry", payload["psychology_tags"])
        self.assertTrue(payload["snapshot_image"]["data_url"].startswith("data:image/svg+xml;base64,"))


if __name__ == "__main__":
    unittest.main()
