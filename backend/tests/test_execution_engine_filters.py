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


class StubExchangeAdapter:
    def __init__(self, exchange_id: str = "binance", *, fail_on_order: bool = False):
        self.exchange_id = exchange_id
        self.fail_on_order = fail_on_order
        self.create_order_calls = []
        self.symbol_info_calls = 0
        self.fetch_order_calls = []

    def fetch_ticker_price(self, symbol: str) -> float:
        return 100.0

    def fetch_symbol_rules(self, symbol: str) -> dict[str, float]:
        self.symbol_info_calls += 1
        return {
            "min_qty": 0.01,
            "max_qty": 1000.0,
            "step_size": 0.01,
            "tick_size": 0.1,
            "min_notional": 10.0,
        }

    def create_order(self, *, symbol: str, side: str, order_type: str, quantity: float, limit_price: float | None = None) -> dict:
        if self.fail_on_order:
            raise RuntimeError(f"{self.exchange_id} unavailable")
        kwargs = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": f"{quantity:.8f}",
        }
        if limit_price is not None:
            kwargs["price"] = f"{limit_price:.8f}"
        self.create_order_calls.append(kwargs)
        return {
            "orderId": f"{self.exchange_id}-123",
            "status": "FILLED",
            "executedQty": f"{quantity:.8f}",
            "origQty": f"{quantity:.8f}",
            "cummulativeQuoteQty": "12.30",
            "price": kwargs.get("price", "100.00"),
            "exchange": self.exchange_id,
        }

    def fetch_order(self, *, symbol: str, order_id: str) -> dict:
        self.fetch_order_calls.append((symbol, order_id))
        return {
            "orderId": order_id,
            "status": "FILLED",
            "executedQty": "0.12000000",
            "origQty": "0.12000000",
            "cummulativeQuoteQty": "12.00",
            "price": "100.00",
            "exchange": self.exchange_id,
        }


class ExecutionEngineFilterTest(unittest.TestCase):
    def _build_engine(self):
        engine = ExecutionEngine(Settings(trading_mode="paper", redis_url="redis://unused", backup_exchanges=[]))
        engine.cache = InMemoryCache()
        engine.queue_manager = StubQueueManager()
        engine.latency_monitor = StubLatencyMonitor()
        engine.router = StubRouter()
        engine.exchange_clients = {"binance": StubExchangeAdapter("binance")}
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

        placed = engine.exchange_clients["binance"].create_order_calls[-1]
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

        self.assertEqual(engine.exchange_clients["binance"].symbol_info_calls, 1)

    def test_falls_back_to_backup_exchange_and_remembers_order_mapping(self):
        engine = ExecutionEngine(
            Settings(
                trading_mode="paper",
                redis_url="redis://unused",
                primary_exchange="binance",
                backup_exchanges=["kraken"],
            )
        )
        engine.cache = InMemoryCache()
        engine.queue_manager = StubQueueManager()
        engine.latency_monitor = StubLatencyMonitor()
        engine.router = StubRouter()
        engine.exchange_clients = {
            "binance": StubExchangeAdapter("binance", fail_on_order=True),
            "kraken": StubExchangeAdapter("kraken"),
        }

        order = engine.place_order(
            symbol="BTCUSDT",
            side="BUY",
            quantity=0.12,
            order_type="MARKET",
        )

        self.assertEqual(order["exchange"], "kraken")
        status = engine.fetch_order_status("BTCUSDT", order["orderId"])
        self.assertEqual(status["exchange"], "kraken")
        self.assertEqual(engine.exchange_clients["kraken"].fetch_order_calls[-1], ("BTCUSDT", "kraken-123"))


if __name__ == "__main__":
    unittest.main()
