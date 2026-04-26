import asyncio
import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.market_data import MarketDataService


class InMemoryCache:
    def __init__(self):
        self.store = {}

    def get_json(self, key):
        return self.store.get(key)

    def set_json(self, key, value, ttl):
        self.store[key] = value


class MarketDataServiceTest(unittest.TestCase):
    def test_fetch_order_book_prefers_stream_cache(self):
        cache = InMemoryCache()
        cache.set_json(
            "stream:book:BTCUSDT",
            {
                "symbol": "BTCUSDT",
                "best_bid": 100.0,
                "best_bid_qty": 3.0,
                "best_ask": 100.1,
                "best_ask_qty": 2.5,
            },
            ttl=30,
        )
        service = MarketDataService(Settings(redis_url="redis://unused"), cache)

        order_book = asyncio.run(service.fetch_order_book("BTCUSDT"))

        self.assertEqual(order_book["bids"][0]["price"], 100.0)
        self.assertEqual(order_book["asks"][0]["price"], 100.1)


if __name__ == "__main__":
    unittest.main()
