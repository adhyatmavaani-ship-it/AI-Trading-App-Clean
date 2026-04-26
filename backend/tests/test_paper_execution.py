import asyncio
import unittest
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.paper_execution import PaperExecutionEngine


class StubMarketDataService:
    async def fetch_latest_price(self, symbol: str) -> float:
        return 100.0


class PaperExecutionTest(unittest.TestCase):
    def test_paper_execution_applies_fees_and_slippage(self):
        engine = PaperExecutionEngine(Settings(), StubMarketDataService())
        order = asyncio.run(
            engine.place_order(
                symbol="BTCUSDT",
                side="BUY",
                quantity=1.0,
                order_type="MARKET",
            )
        )
        self.assertEqual(order["mode"], "paper")
        self.assertGreater(float(order["price"]), 100.0)
        self.assertGreater(order["feePaid"], 0)
        self.assertEqual(order["filledRatio"], 1.0)

    def test_marketable_limit_order_does_not_fill_worse_than_simulated_market_price(self):
        engine = PaperExecutionEngine(Settings(), StubMarketDataService())
        order = asyncio.run(
            engine.place_order(
                symbol="BTCUSDT",
                side="BUY",
                quantity=1.0,
                order_type="LIMIT",
                limit_price=105.0,
            )
        )

        self.assertEqual(order["status"], "PARTIALLY_FILLED")
        self.assertLess(float(order["price"]), 105.0)


if __name__ == "__main__":
    unittest.main()
