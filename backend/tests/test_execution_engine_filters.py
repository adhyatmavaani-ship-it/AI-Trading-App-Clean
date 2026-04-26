import unittest
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.execution_engine import ExecutionEngine


class InMemoryCache:
    def __init__(self):
        self.store = {}

    def get_json(self, key):
        return self.store.get(key)

    def set_json(self, key, value, ttl):
        self.store[key] = value

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ttl=None):
        self.store[key] = value


class StubQueueManager:
    def throttle(self, scope: str) -> int:
        return 0


class StubLatencyMonitor:
    def __init__(self):
        self.metrics = []

    def record_sync(self, name: str, value: float) -> None:
        self.metrics.append((name, value))


class StubRouter:
    def route(self, symbol: str, side: str, quantity: float) -> dict:
        return {"broadcast_delay_ms": 0}


class StubClient:
    def __init__(self):
        self.create_order_calls = []
        self.symbol_info_calls = 0

    def get_symbol_ticker(self, symbol: str) -> dict:
        return {"price": "100.00"}

    def get_symbol_info(self, symbol: str) -> dict:
        self.symbol_info_calls += 1
        return {
            "filters": [
                {"filterType": "LOT_SIZE", "minQty": "0.01000000", "maxQty": "1000.00000000", "stepSize": "0.01000000"},
                {"filterType": "PRICE_FILTER", "tickSize": "0.10000000"},
                {"filterType": "MIN_NOTIONAL", "minNotional": "10.00"},
            ]
        }

    def create_order(self, **kwargs) -> dict:
        self.create_order_calls.append(kwargs)
        return {
            "orderId": "123",
            "status": "FILLED",
            "executedQty": kwargs["quantity"],
            "cummulativeQuoteQty": "12.30",
            "price": kwargs.get("price", "100.00"),
        }


class ExecutionEngineFilterTest(unittest.TestCase):
    def _build_engine(self):
        engine = ExecutionEngine(Settings(trading_mode="paper", redis_url="redis://unused"))
        engine.client = StubClient()
        engine.cache = InMemoryCache()
        engine.queue_manager = StubQueueManager()
        engine.latency_monitor = StubLatencyMonitor()
        engine.router = StubRouter()
        return engine

    def test_limit_order_is_normalized_to_exchange_filters(self):
        engine = self._build_engine()

        engine.place_order(
            symbol="BTCUSDT",
            side="BUY",
            quantity=0.123456,
            order_type="LIMIT",
            limit_price=100.23,
        )

        placed = engine.client.create_order_calls[-1]
        self.assertEqual(placed["quantity"], "0.12000000")
        self.assertEqual(placed["price"], "100.20000000")

    def test_market_order_below_exchange_notional_is_rejected(self):
        engine = self._build_engine()

        with self.assertRaisesRegex(ValueError, "minimum notional"):
            engine.place_order(
                symbol="BTCUSDT",
                side="BUY",
                quantity=0.05,
                order_type="MARKET",
            )

    def test_symbol_rules_are_cached_after_first_lookup(self):
        engine = self._build_engine()

        engine.place_order(
            symbol="BTCUSDT",
            side="BUY",
            quantity=0.12,
            order_type="MARKET",
        )
        engine.place_order(
            symbol="BTCUSDT",
            side="SELL",
            quantity=0.12,
            order_type="MARKET",
        )

        self.assertEqual(engine.client.symbol_info_calls, 1)


if __name__ == "__main__":
    unittest.main()
