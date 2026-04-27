import asyncio
import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.market_data import MarketDataService


class _FakeCache:
    def __init__(self) -> None:
        self.payloads: dict[str, dict] = {}

    def get_json(self, key: str):
        return self.payloads.get(key)

    def set_json(self, key: str, value, ttl: int | None = None) -> None:
        self.payloads[key] = value


class MarketDataServiceTest(unittest.TestCase):
    def test_simulated_mode_reports_simulated_fetch_sources(self):
        settings = Settings(market_data_mode="simulated")
        service = MarketDataService(settings, _FakeCache())

        latest_price = asyncio.run(service.fetch_latest_price("BTCUSDT"))
        frames = asyncio.run(service.fetch_multi_timeframe_ohlcv("BTCUSDT", intervals=("1m",)))
        order_book = asyncio.run(service.fetch_order_book("BTCUSDT"))
        diagnostics = service.diagnostics()

        self.assertGreater(latest_price, 0.0)
        self.assertIn("1m", frames)
        self.assertTrue(order_book.get("bids"))
        self.assertEqual(diagnostics["resolved_mode"], "simulated")
        self.assertTrue(diagnostics["using_mock_data"])
        self.assertEqual(diagnostics["last_fetch_details"]["price:BTCUSDT"]["source"], "simulated")
        self.assertEqual(diagnostics["last_fetch_details"]["ohlcv:BTCUSDT:1m"]["source"], "simulated")
        self.assertEqual(diagnostics["last_fetch_details"]["order_book:BTCUSDT"]["source"], "simulated")

    def test_inject_test_market_move_updates_cached_stream_and_candles(self):
        settings = Settings(market_data_mode="simulated")
        cache = _FakeCache()
        service = MarketDataService(settings, cache)

        asyncio.run(service.fetch_multi_timeframe_ohlcv("BTCUSDT", intervals=("5m",)))
        result = service.inject_test_market_move("BTCUSDT", change=-0.02, volume_multiplier=4.0, intervals=("5m",))

        self.assertEqual(result["symbol"], "BTCUSDT")
        self.assertLess(result["updated_price"], result["reference_price"])
        self.assertAlmostEqual(cache.payloads["stream:btcusdt@trade"]["p"], result["updated_price"], places=6)
        cached_rows = cache.payloads["ohlcv:BTCUSDT:5m"]["rows"]
        self.assertTrue(cached_rows)
        last_row = cached_rows[-1]
        self.assertAlmostEqual(float(last_row["close"]), float(result["updated_price"]), places=6)
        self.assertEqual(service.diagnostics()["last_fetch_details"]["price:BTCUSDT"]["source"], "test_override")
        self.assertEqual(service.diagnostics()["last_fetch_details"]["ohlcv:BTCUSDT:5m"]["source"], "test_override")


if __name__ == "__main__":
    unittest.main()
