import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.market_universe_scanner import MarketUniverseScanner
from app.services.redis_cache import RedisCache
from app.services.scanner_service import ScannerService


class StubTickerMarketData:
    async def fetch_market_tickers(self, *, quote_asset: str | None = None, limit: int | None = None):
        items = [
            {"symbol": "BTCUSDT", "base": "BTC", "quote": "USDT", "price": 68000.0, "change_pct": 2.2, "quote_volume": 150_000_000.0, "exchange": "binance"},
            {"symbol": "ETHUSDT", "base": "ETH", "quote": "USDT", "price": 3200.0, "change_pct": 1.9, "quote_volume": 110_000_000.0, "exchange": "binance"},
            {"symbol": "SOLUSDT", "base": "SOL", "quote": "USDT", "price": 145.0, "change_pct": 6.4, "quote_volume": 95_000_000.0, "exchange": "binance"},
            {"symbol": "DOGEUSDT", "base": "DOGE", "quote": "USDT", "price": 0.18, "change_pct": 7.1, "quote_volume": 85_000_000.0, "exchange": "binance"},
            {"symbol": "XRPUSDT", "base": "XRP", "quote": "USDT", "price": 0.62, "change_pct": 5.6, "quote_volume": 82_000_000.0, "exchange": "binance"},
            {"symbol": "ADAUSDT", "base": "ADA", "quote": "USDT", "price": 0.45, "change_pct": 4.8, "quote_volume": 78_000_000.0, "exchange": "binance"},
            {"symbol": "BNBUSDT", "base": "BNB", "quote": "USDT", "price": 590.0, "change_pct": 3.2, "quote_volume": 74_000_000.0, "exchange": "binance"},
            {"symbol": "AVAXUSDT", "base": "AVAX", "quote": "USDT", "price": 38.0, "change_pct": 4.4, "quote_volume": 70_000_000.0, "exchange": "binance"},
            {"symbol": "PEPEUSDT", "base": "PEPE", "quote": "USDT", "price": 0.00001, "change_pct": 8.1, "quote_volume": 62_000_000.0, "exchange": "binance"},
        ]
        return items[:limit] if limit is not None else items

    async def fetch_multi_timeframe_ohlcv(self, symbol: str, intervals=("5m", "15m")):
        frames = {}
        for offset, interval in enumerate(intervals):
            rows = []
            for candle_index in range(24):
                rows.append(
                    {
                        "open_time": 1714212000000 + (candle_index * 300000),
                        "close_time": 1714212300000 + (candle_index * 300000),
                        "open": 100.0 + offset + candle_index * 0.1,
                        "high": 100.8 + offset + candle_index * 0.1,
                        "low": 99.2 + offset + candle_index * 0.1,
                        "close": 100.4 + offset + candle_index * 0.12,
                        "volume": 20.0 + candle_index,
                    }
                )
            frames[interval] = pd.DataFrame(rows)
        return frames

    async def fetch_latest_price(self, symbol: str):
        return 100.0


class StubUserExperienceEngine:
    def readiness(self, limit: int = 8):
        return [{"symbol": "SOLUSDT", "readiness": 72.0}, {"symbol": "ETHUSDT", "readiness": 68.0}][:limit]


class ScannerServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_scanner_keeps_fixed_symbols_and_rotates_ranked_candidates(self):
        settings = Settings()
        settings.scanner_fixed_symbols = ["BTCUSDT", "ETHUSDT"]
        settings.scanner_active_symbol_limit = 6
        settings.scanner_candidate_limit = 8
        settings.scanner_rotation_hours = 4
        settings.scanner_refresh_minutes = 15
        service = ScannerService(
            settings=settings,
            cache=RedisCache(""),
            market_data=StubTickerMarketData(),
        )

        payload = await service.state(force_refresh=True)

        self.assertEqual(payload["fixed_symbols"], ["BTCUSDT", "ETHUSDT"])
        self.assertEqual(payload["active_symbols"][:2], ["BTCUSDT", "ETHUSDT"])
        self.assertEqual(len(payload["active_symbols"]), 6)
        self.assertEqual(len(payload["rotating_symbols"]), 4)
        self.assertIn("SOLUSDT", payload["rotating_symbols"])
        self.assertGreater(payload["seconds_until_rotation"], 0)
        self.assertGreater(payload["candidates"][0]["potential_score"], 0.0)

    async def test_market_universe_snapshot_includes_scanner_metadata(self):
        settings = Settings()
        settings.scanner_fixed_symbols = ["BTCUSDT", "ETHUSDT"]
        settings.scanner_active_symbol_limit = 5
        settings.scanner_candidate_limit = 8
        service = ScannerService(
            settings=settings,
            cache=RedisCache(""),
            market_data=StubTickerMarketData(),
        )
        scanner = MarketUniverseScanner(
            settings=settings,
            market_data=StubTickerMarketData(),
            user_experience_engine=StubUserExperienceEngine(),
            scanner_service=service,
        )

        payload = await scanner.snapshot(limit=5)

        self.assertEqual(payload["count"], 5)
        self.assertIn("scanner", payload)
        self.assertEqual(payload["scanner"]["active_symbols"][:2], ["BTCUSDT", "ETHUSDT"])
        self.assertTrue(payload["scanner"]["candidates"])
        self.assertIn("potential_score", payload["items"][0])


if __name__ == "__main__":
    unittest.main()
