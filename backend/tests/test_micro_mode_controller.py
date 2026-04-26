import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.micro_mode_controller import MicroModeController


class InMemoryCache:
    def __init__(self):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ttl=None):
        self.store[key] = value

    def increment(self, key, ttl):
        self.store[key] = int(self.store.get(key, 0)) + 1
        return self.store[key]

    def get_json(self, key):
        return self.store.get(key)

    def set_json(self, key, value, ttl):
        self.store[key] = value


class MicroModeControllerTest(unittest.TestCase):
    def test_single_trade_mode_sizes_large_fraction_for_small_accounts(self):
        controller = MicroModeController(
            Settings(
                default_portfolio_balance=25,
                micro_single_trade_capital_threshold=50,
                exchange_min_notional=10,
            ),
            InMemoryCache(),
        )
        size = controller.determine_trade_size(
            user_id="u1",
            account_equity=25,
            latest_price=100,
            requested_notional=5,
            slippage_bps=50,
        )
        self.assertFalse(size["skip"])
        self.assertGreaterEqual(size["trade_notional"], 17.5)
        self.assertEqual(size["mode"], "single_trade")

    def test_skips_when_below_exchange_minimum(self):
        controller = MicroModeController(
            Settings(
                default_portfolio_balance=12,
                micro_single_trade_capital_threshold=50,
                exchange_min_notional=15,
            ),
            InMemoryCache(),
        )
        size = controller.determine_trade_size(
            user_id="u1",
            account_equity=12,
            latest_price=100,
            requested_notional=3,
            slippage_bps=100,
        )
        self.assertTrue(size["skip"])
        self.assertEqual(size["reason"], "below_exchange_minimum")


if __name__ == "__main__":
    unittest.main()
