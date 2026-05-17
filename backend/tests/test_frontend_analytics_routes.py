import asyncio
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
    from app.services.container import get_container


class StubCache:
    def __init__(self):
        self.store = {}

    def get_json(self, key):
        return self.store.get(key)

    def set_json(self, key, value, ttl):
        self.store[key] = value

    def keys(self, pattern: str):
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            return [key for key in self.store if key.startswith(prefix)]
        return [key for key in self.store if key == pattern]


class StubAnalyticsService:
    def active_trades(self, user_id: str):
        return [
            {
                "trade_id": "t1",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "entry": 100.25,
                "created_at": "2026-04-27T10:00:00+00:00",
                "confidence_score": 0.84,
            }
        ]

    def trade_history(self, user_id: str, limit: int = 100):
        return [
            {
                "trade_id": "t1",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "entry": 100.25,
                "exit": 101.75,
                "profit_pct": 1.25,
                "closed_at": "2026-04-27T11:00:00+00:00",
                "exit_reason": "structure_break",
                "confidence_score": 0.84,
            }
        ]

    def summary(self, user_id: str):
        return {"user_id": user_id, "win_rate": 0.6, "expectancy": 0.4, "best_symbols": ["BTCUSDT"], "best_regime": "TRENDING", "worst_regime": "RANGING", "regime_win_rates": {"TRENDING": 0.64, "RANGING": 0.42}, "worst_exit_reasons": ["volume_reversal"], "most_profitable_setup": "structure + momentum", "false_signal_rate": 0.25, "capital_utilization": 0.42, "risk_exposure": 0.03, "correlation_risk": 0.6, "regime_distribution": {"TRENDING": 0.5, "RANGING": 0.3, "HIGH_VOL": 0.2}}

    def performance(self, user_id: str):
        return {"summary": {"user_id": user_id}, "weights": {"structure": 0.4, "momentum": 0.3, "volume": 0.3}}


class StubUserExperienceEngine:
    def latest(self):
        return {
            "status": "scanning",
            "bot_state": "SCANNING",
            "message": "BTC checked -> weak volume, skipped",
            "intent": "Watching BTC for stronger volume",
            "readiness": 41,
            "confidence_history": self.confidence_history(symbol="BTCUSDT"),
        }

    def history(self, limit: int = 25):
        return [
            {
                "status": "scanning",
                "message": "Scanning BTC...",
                "symbol": "BTCUSDT",
                "timestamp": "2026-04-27T09:55:00+00:00",
                "confidence": 0.41,
                "readiness": 32.0,
                "reason": "setup forming",
            },
            {
                "status": "almost_trade",
                "message": "ETH almost triggered trade",
                "symbol": "ETHUSDT",
                "timestamp": "2026-04-27T10:05:00+00:00",
                "confidence": 0.68,
                "readiness": 68.0,
            },
            {
                "status": "almost_trade",
                "message": "BTC almost triggered trade",
                "symbol": "BTCUSDT",
                "timestamp": "2026-04-27T10:15:00+00:00",
                "confidence": 0.77,
                "readiness": 74.0,
                "reason": "volume confirmation missing",
                "intent": "Waiting for BTC confirmation",
            },
        ][:limit]

    def readiness(self, limit: int = 8):
        return [
            {
                "symbol": "ETHUSDT",
                "readiness": 68,
                "status": "almost_trade",
                "confidence_history": self.confidence_history(symbol="ETHUSDT"),
            },
            {
                "symbol": "BTCUSDT",
                "readiness": 41,
                "status": "scanning",
                "confidence_history": self.confidence_history(symbol="BTCUSDT"),
            },
        ][:limit]

    def confidence_history(self, symbol: str | None = None, limit: int = 24):
        histories = {
            "BTCUSDT": [
                {
                    "ts": 1777283700,
                    "score": 0.41,
                    "is_ghost": True,
                    "symbol": "BTCUSDT",
                    "message": "Scanning BTC...",
                    "reason": "setup forming",
                },
                {
                    "ts": 1777284900,
                    "score": 0.77,
                    "is_ghost": True,
                    "symbol": "BTCUSDT",
                    "message": "BTC almost triggered trade",
                    "reason": "volume confirmation missing",
                },
            ],
            "ETHUSDT": [
                {
                    "ts": 1777284300,
                    "score": 0.68,
                    "is_ghost": True,
                    "symbol": "ETHUSDT",
                    "message": "ETH almost triggered trade",
                },
            ],
            None: [
                {"ts": 1777283700, "score": 0.41, "is_ghost": True, "symbol": "BTCUSDT"},
                {"ts": 1777284300, "score": 0.68, "is_ghost": True, "symbol": "ETHUSDT"},
                {"ts": 1777284900, "score": 0.77, "is_ghost": True, "symbol": "BTCUSDT"},
            ],
        }
        return list(histories.get(symbol, histories[None]))[:limit]


class StubMarketData:
    def __init__(self):
        self.last_move = None

    def diagnostics(self):
        return {"resolved_mode": "simulated", "last_fetch_details": {}}

    async def fetch_latest_price(self, symbol: str):
        return 100.0

    async def fetch_order_book(self, symbol: str):
        return {"bids": [{"price": 99.5, "qty": 1.0}], "asks": [{"price": 100.5, "qty": 1.0}]}

    async def fetch_multi_timeframe_ohlcv(self, symbol: str, intervals=("1m", "5m", "15m")):
        frames = {}
        for index, interval in enumerate(intervals):
            base_open = 100.0 + index
            rows = []
            for candle_index in range(24):
                rows.append(
                    {
                        "open_time": 1714212000000 + (candle_index * 300000),
                        "close_time": 1714212300000 + (candle_index * 300000),
                        "open": base_open + candle_index * 0.1,
                        "high": base_open + candle_index * 0.1 + 1.0,
                        "low": base_open + candle_index * 0.1 - 1.0,
                        "close": base_open + candle_index * 0.1 + 0.4,
                        "volume": 10 + candle_index,
                    }
                )
            frames[interval] = pd.DataFrame(rows)
        return frames

    def inject_test_market_move(self, symbol: str, *, change: float, volume_multiplier: float = 3.0, intervals=("1m", "5m", "15m", "1h")):
        self.last_move = {
            "symbol": symbol,
            "change": change,
            "volume_multiplier": volume_multiplier,
            "intervals": list(intervals),
        }
        return {
            "symbol": symbol,
            "reference_price": 100.0,
            "updated_price": 98.0,
            "change": change,
            "volume_multiplier": volume_multiplier,
            "updated_intervals": {"5m": 300},
        }


class StubActiveTradeMonitor:
    def __init__(self):
        self.runs = 0

    async def run_once(self):
        self.runs += 1


class StubMarketUniverseScanner:
    async def snapshot(self, limit: int | None = None):
        items = [
            {
                "symbol": "ETHUSDT",
                "price": 2500.0,
                "change_pct": 1.8,
                "volume_ratio": 1.4,
                "volatility_pct": 2.2,
                "trend_pct": 3.4,
                "quote_volume": 2500000.0,
                "category": "high_volatility",
            },
            {
                "symbol": "BTCUSDT",
                "price": 65000.0,
                "change_pct": 1.1,
                "volume_ratio": 1.2,
                "volatility_pct": 1.6,
                "trend_pct": 2.1,
                "quote_volume": 5000000.0,
                "category": "top_gainer",
            },
        ][: max(1, limit or 2)]
        return {
            "count": len(items),
            "items": items,
            "categories": {
                "top_gainers": items,
                "high_volatility": items[:1],
                "ai_picks": items,
            },
        }

    async def summary(self, limit: int | None = None):
        return {
            "sentiment_score": 37.5,
            "sentiment_label": "BULLISH",
            "market_breadth": 0.5,
            "avg_change_pct": 1.45,
            "avg_volatility_pct": 1.9,
            "participation_score": 0.72,
            "confidence_score": 0.68,
            "ticker": [
                {"symbol": "BTCUSDT", "price": 65000.0, "change_pct": 1.1},
                {"symbol": "ETHUSDT", "price": 2500.0, "change_pct": 1.8},
            ][: max(1, min(limit or 2, 2))],
            "heatmap": [
                {"symbol": "BTCUSDT", "change_pct": 1.1, "intensity": 0.3},
                {"symbol": "ETHUSDT", "change_pct": 1.8, "intensity": 0.45},
            ],
            "top_movers": [
                {
                    "symbol": "ETHUSDT",
                    "price": 2500.0,
                    "change_pct": 1.8,
                    "volume_ratio": 1.4,
                    "volatility_pct": 2.2,
                    "trend_pct": 3.4,
                    "quote_volume": 2500000.0,
                    "category": "high_volatility",
                }
            ],
        }


class StubTradingOrchestrator:
    def __init__(self):
        self.calls = 0
        self.delay_seconds = 0.0

    async def generate_live_signals(self, limit: int = 3):
        self.calls += 1
        if self.delay_seconds > 0:
            await asyncio.sleep(self.delay_seconds)
        return []


class StubContainer:
    def __init__(self):
        self.cache = StubCache()
        self.settings = SimpleNamespace(
            live_signals_route_timeout_seconds=2.5,
            live_signals_response_cache_ttl_seconds=3,
            slow_operation_threshold_seconds=1.0,
            default_portfolio_balance=10_000.0,
            effective_debug_routes_enabled=True,
            websocket_symbols=["BTCUSDT", "ETHUSDT", "SOLUSDT"],
            signal_min_publish_confidence=0.2,
            alpha_trade_threshold=40.0,
            exchange_min_notional=10.0,
        )
        self.analytics_service = StubAnalyticsService()
        self.user_experience_engine = StubUserExperienceEngine()
        self.market_data = StubMarketData()
        self.active_trade_monitor = StubActiveTradeMonitor()
        self.market_universe_scanner = StubMarketUniverseScanner()
        self.trading_orchestrator = StubTradingOrchestrator()
        self.signal_broadcaster = None


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
        self.container = StubContainer()
        app.dependency_overrides[get_container] = lambda: self.container
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

    def test_market_candles_exposes_professional_chart_payload(self):
        response = self.client.get(
            "/v1/market/candles?symbol=BTCUSDT&interval=3m&user_id=alice",
            headers={"X-API-Key": "route-token"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["symbol"], "BTCUSDT")
        self.assertEqual(payload["interval"], "3m")
        self.assertEqual(payload["chart_engine"], "custom_canvas_pro")
        self.assertIn("market_regime", payload)
        self.assertIn("opportunity", payload)
        self.assertIn("execution_guide", payload)
        self.assertIn("strategy_state", payload)
        self.assertIn("ai_feed", payload)
        self.assertIn("overlays", payload)
        self.assertIn("assistant_modes", payload)
        self.assertTrue(payload["candles"])

    def test_market_assistant_mode_round_trip(self):
        set_response = self.client.post(
            "/v1/market/assistant-mode",
            json={"mode": "full_auto"},
            headers={"X-API-Key": "route-token"},
        )
        get_response = self.client.get(
            "/v1/market/assistant-mode",
            headers={"X-API-Key": "route-token"},
        )

        self.assertEqual(set_response.status_code, 200)
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(set_response.json()["mode"], "FULL_AUTO")
        self.assertEqual(get_response.json()["mode"], "FULL_AUTO")

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
        self.assertGreaterEqual(len(response.json()["confidence_history"]), 1)

    def test_activity_history_endpoint(self):
        response = self.client.get("/v1/activity/history", headers={"X-API-Key": "route-token"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 3)

    def test_activity_readiness_endpoint(self):
        response = self.client.get("/v1/activity/readiness", headers={"X-API-Key": "route-token"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["symbol"], "ETHUSDT")
        self.assertIn("confidence_history", response.json()["items"][0])

    def test_live_signals_prefers_cached_signals_and_skips_live_generation(self):
        self.container.cache.store["signal:latest:btc"] = {
            "signal_id": "btc-cached",
            "symbol": "BTCUSDT",
            "action": "BUY",
            "strategy": "MOMENTUM_BREAKOUT",
            "confidence": 0.82,
            "alpha_score": 88.0,
            "regime": "TRENDING",
            "price": 64000.0,
            "signal_version": 3,
            "published_at": "2026-04-27T10:15:00+00:00",
            "decision_reason": "cached signal",
            "degraded_mode": False,
            "required_tier": "free",
            "min_balance": 0.0,
            "low_confidence": False,
        }
        self.container.cache.store["signal:latest:eth"] = {
            "signal_id": "eth-cached",
            "symbol": "ETHUSDT",
            "action": "SELL",
            "strategy": "MEAN_REVERSION",
            "confidence": 0.77,
            "alpha_score": 81.0,
            "regime": "RANGING",
            "price": 2500.0,
            "signal_version": 4,
            "published_at": "2026-04-27T10:14:00+00:00",
            "decision_reason": "cached signal",
            "degraded_mode": False,
            "required_tier": "free",
            "min_balance": 0.0,
            "low_confidence": False,
        }
        self.container.cache.store["signal:latest:sol"] = {
            "signal_id": "sol-cached",
            "symbol": "SOLUSDT",
            "action": "BUY",
            "strategy": "TREND_PULLBACK",
            "confidence": 0.75,
            "alpha_score": 79.0,
            "regime": "TRENDING",
            "price": 150.0,
            "signal_version": 5,
            "published_at": "2026-04-27T10:13:00+00:00",
            "decision_reason": "cached signal",
            "degraded_mode": False,
            "required_tier": "free",
            "min_balance": 0.0,
            "low_confidence": False,
        }

        response = self.client.get("/v1/signals/live?limit=3", headers={"X-API-Key": "route-token"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 3)
        self.assertEqual(payload["items"][0]["signal_id"], "btc-cached")
        self.assertEqual(payload["items"][0]["quality"], "approved")
        self.assertTrue(payload["items"][0]["execution_allowed"])
        self.assertEqual(self.container.trading_orchestrator.calls, 0)

    def test_live_signals_returns_fallback_when_generation_times_out(self):
        self.container.settings.live_signals_route_timeout_seconds = 0.01
        self.container.trading_orchestrator.delay_seconds = 0.05

        response = self.client.get("/v1/signals/live?limit=3", headers={"X-API-Key": "route-token"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(payload["count"], 1)
        self.assertTrue(payload["items"][0]["degraded_mode"])
        self.assertEqual(payload["items"][0]["quality"], "degraded")
        self.assertFalse(payload["items"][0]["execution_allowed"])
        self.assertEqual(payload["items"][0]["rejection_reason"], "live_generation_unavailable")
        self.assertEqual(self.container.trading_orchestrator.calls, 1)

    def test_mock_price_move_endpoint(self):
        response = self.client.post(
            "/v1/test/mock-price-move",
            headers={"X-API-Key": "route-token"},
            json={"symbol": "BTCUSDT", "change": -0.02},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["symbol"], "BTCUSDT")
        self.assertTrue(payload["monitor_ran"])
        self.assertEqual(payload["move"]["change"], -0.02)

    def test_market_candles_endpoint(self):
        response = self.client.get(
            "/v1/market/candles?symbol=btcusdt&interval=5m&limit=20&user_id=alice",
            headers={"X-API-Key": "route-token"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["symbol"], "BTCUSDT")
        self.assertEqual(payload["interval"], "5m")
        self.assertEqual(len(payload["candles"]), 20)
        self.assertGreaterEqual(len(payload["confidence_intervals"]), 1)
        self.assertGreaterEqual(len(payload["confidence_history"]), 1)
        marker_types = [item["marker_type"] for item in payload["markers"]]
        self.assertIn("ENTRY", marker_types)
        self.assertIn("EXIT", marker_types)
        self.assertIn("REJECTED_SETUP", marker_types)
        entry_marker = next(item for item in payload["markers"] if item["marker_type"] == "ENTRY")
        exit_marker = next(item for item in payload["markers"] if item["marker_type"] == "EXIT")
        ghost_markers = [item for item in payload["markers"] if item["marker_type"] == "REJECTED_SETUP"]
        ghost_marker = next(
            item for item in ghost_markers if item.get("reason") == "volume confirmation missing"
        )
        self.assertEqual(entry_marker["timestamp"], "2026-04-27T10:00:00+00:00")
        self.assertEqual(exit_marker["timestamp"], "2026-04-27T11:00:00+00:00")
        self.assertAlmostEqual(entry_marker["confidence_score"], 0.84, places=6)
        self.assertEqual(ghost_marker["marker_style"], "ghost")
        self.assertAlmostEqual(ghost_marker["confidence_score"], 0.77, places=6)
        self.assertEqual(ghost_marker["reason"], "volume confirmation missing")
        self.assertTrue(payload["confidence_history"][-1]["is_ghost"])
        first_interval = payload["confidence_intervals"][0]
        self.assertIn(first_interval["zone_type"], {"STRONG_CONVICTION", "SOFT_CONVICTION"})
        self.assertGreaterEqual(first_interval["score"], 0.6)
        self.assertLessEqual(first_interval["start_ts"], first_interval["end_ts"])

    def test_market_universe_endpoint(self):
        response = self.client.get(
            "/v1/market/universe?limit=8",
            headers={"X-API-Key": "route-token"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(payload["count"], 1)
        self.assertIn("categories", payload)
        self.assertIn("ai_picks", payload["categories"])
        self.assertEqual(payload["categories"]["ai_picks"][0]["symbol"], "ETHUSDT")

    def test_market_summary_get_endpoint(self):
        response = self.client.get(
            "/v1/market/summary?limit=8",
            headers={"X-API-Key": "route-token"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["sentiment_label"], "BULLISH")
        self.assertAlmostEqual(payload["sentiment_score"], 37.5, places=6)
        self.assertEqual(payload["ticker"][0]["symbol"], "BTCUSDT")
        self.assertGreaterEqual(len(payload["confidence_history"]), 1)

    def test_market_summary_post_endpoint(self):
        response = self.client.post(
            "/v1/market/summary",
            headers={"X-API-Key": "route-token"},
            json={"limit": 8},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("heatmap", payload)
        self.assertIn("top_movers", payload)


if __name__ == "__main__":
    unittest.main()
