import asyncio
import unittest
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.schemas.trading import FeatureSnapshot
from app.services.redis_state_manager import RedisStateManager
from app.workers.trade_monitor_worker import ActiveTradeMonitorWorker


class InMemoryCache:
    def __init__(self):
        self.store = {}

    def get_json(self, key):
        return self.store.get(key)

    def set_json(self, key, value, ttl):
        self.store[key] = value

    def delete(self, key):
        self.store.pop(key, None)

    def keys(self, pattern):
        prefix = pattern.replace("*", "")
        return [key for key in self.store if key.startswith(prefix)]


class StubMarketData:
    def __init__(self, frame: pd.DataFrame):
        self.frame = frame

    async def fetch_multi_timeframe_ohlcv(self, symbol: str, intervals=("5m", "15m", "1h")):
        return {interval: self.frame.copy() for interval in intervals}

    async def fetch_order_book(self, symbol: str):
        return {
            "bids": [{"price": 99.9, "qty": 10.0}],
            "asks": [{"price": 100.1, "qty": 10.0}],
        }


class StubFeaturePipeline:
    def __init__(self, snapshot: FeatureSnapshot):
        self.snapshot = snapshot

    def build(self, symbol: str, frames, order_book):
        return self.snapshot


class StubOrchestrator:
    def __init__(self):
        self.updated = []
        self.closed = []

    def update_active_trade_state(self, trade_id: str, payload: dict) -> None:
        self.updated.append((trade_id, payload))

    def close_trade_position(
        self,
        *,
        user_id: str,
        trade_id: str,
        exit_price: float,
        reason: str,
        exit_fee: float = 0.0,
        closed_quantity: float | None = None,
    ):
        self.closed.append(
            {
                "user_id": user_id,
                "trade_id": trade_id,
                "exit_price": exit_price,
                "reason": reason,
                "exit_fee": exit_fee,
                "closed_quantity": closed_quantity,
            }
        )


class ActiveTradeMonitorWorkerTest(unittest.TestCase):
    def _frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "open": [100.0, 101.0, 102.0, 103.0, 104.0],
                "high": [101.0, 102.0, 103.0, 104.0, 110.0],
                "low": [99.5, 100.5, 101.5, 102.5, 103.5],
                "close": [100.8, 101.7, 102.6, 103.8, 109.2],
                "volume": [1000.0, 1050.0, 1100.0, 1150.0, 2500.0],
            }
        )

    def test_structure_break_closes_trade_early(self):
        settings = Settings(redis_url="redis://unused")
        cache = InMemoryCache()
        redis_state_manager = RedisStateManager(settings, cache)
        trade = {
            "trade_id": "t1",
            "user_id": "u1",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "entry": 100.0,
            "stop_loss": 95.0,
            "max_profit": 0.0,
        }
        redis_state_manager.save_active_trade("t1", trade)
        redis_state_manager.register_monitored_trade("t1", {"trade_id": "t1"})
        snapshot = FeatureSnapshot(
            symbol="BTCUSDT",
            price=98.5,
            timestamp=pd.Timestamp.now(tz="UTC").to_pydatetime(),
            regime="TRENDING",
            regime_confidence=0.9,
            volatility=0.01,
            atr=1.5,
            order_book_imbalance=-0.2,
            features={"15m_structure_bearish": 1.0, "15m_structure_bullish": 0.0, "5m_atr": 1.5},
        )
        orchestrator = StubOrchestrator()
        worker = ActiveTradeMonitorWorker(
            settings=settings,
            redis_state_manager=redis_state_manager,
            market_data=StubMarketData(self._frame()),
            feature_pipeline=StubFeaturePipeline(snapshot),
            trading_orchestrator=orchestrator,
        )

        asyncio.run(worker.run_once())

        self.assertEqual(len(orchestrator.closed), 1)
        self.assertEqual(orchestrator.closed[0]["reason"], "structure_break")
        self.assertTrue(orchestrator.updated)
        self.assertEqual(orchestrator.updated[-1][1]["exit_type"], "early_exit")

    def test_partial_take_profit_locks_trade_state(self):
        settings = Settings(redis_url="redis://unused")
        cache = InMemoryCache()
        redis_state_manager = RedisStateManager(settings, cache)
        trade = {
            "trade_id": "t2",
            "user_id": "u1",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "entry": 100.0,
            "stop_loss": 95.0,
            "initial_stop_loss": 95.0,
            "max_profit": 0.01,
        }
        redis_state_manager.save_active_trade("t2", trade)
        redis_state_manager.register_monitored_trade("t2", {"trade_id": "t2"})
        snapshot = FeatureSnapshot(
            symbol="BTCUSDT",
            price=109.2,
            timestamp=pd.Timestamp.now(tz="UTC").to_pydatetime(),
            regime="TRENDING",
            regime_confidence=0.9,
            volatility=0.01,
            atr=2.0,
            order_book_imbalance=0.2,
            features={"15m_structure_bearish": 0.0, "15m_structure_bullish": 1.0, "5m_atr": 2.0},
        )
        orchestrator = StubOrchestrator()
        worker = ActiveTradeMonitorWorker(
            settings=settings,
            redis_state_manager=redis_state_manager,
            market_data=StubMarketData(self._frame()),
            feature_pipeline=StubFeaturePipeline(snapshot),
            trading_orchestrator=orchestrator,
        )

        asyncio.run(worker.run_once())

        self.assertEqual(len(orchestrator.closed), 1)
        self.assertEqual(orchestrator.closed[0]["reason"], "partial_take_profit")
        self.assertTrue(orchestrator.updated)
        updated_trade = orchestrator.updated[-1][1]
        self.assertGreaterEqual(updated_trade["stop_loss"], 100.5)
        self.assertGreater(updated_trade["max_profit"], 0.01)
        self.assertTrue(updated_trade["partial_take_profit_taken"])
        self.assertEqual(updated_trade["exit_type"], "partial_take_profit")


if __name__ == "__main__":
    unittest.main()
