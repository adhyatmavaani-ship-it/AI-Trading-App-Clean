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


class StubExchangeClient:
    def __init__(self, exchange_id: str, *, fail_price: bool = False):
        self.exchange_id = exchange_id
        self.fail_price = fail_price

    def fetch_ticker_price(self, symbol: str) -> float:
        if self.fail_price:
            raise RuntimeError(f"{self.exchange_id} unavailable")
        return 101.25

    def fetch_order_book(self, *, symbol: str, limit: int = 20) -> dict:
        return {
            "bids": [{"price": 101.2, "qty": 4.0}],
            "asks": [{"price": 101.3, "qty": 5.0}],
        }

    def fetch_ohlcv(self, *, symbol: str, interval: str, limit: int = 300):
        raise NotImplementedError


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

    def test_fetch_latest_price_falls_back_to_backup_exchange(self):
        cache = InMemoryCache()
        service = MarketDataService(
            Settings(
                redis_url="redis://unused",
                primary_exchange="binance",
                backup_exchanges=["kraken"],
            ),
            cache,
        )
        service.exchange_clients = {
            "binance": StubExchangeClient("binance", fail_price=True),
            "kraken": StubExchangeClient("kraken"),
        }

        price = asyncio.run(service.fetch_latest_price("BTCUSDT"))

        self.assertEqual(price, 101.25)


if __name__ == "__main__":
    unittest.main()
