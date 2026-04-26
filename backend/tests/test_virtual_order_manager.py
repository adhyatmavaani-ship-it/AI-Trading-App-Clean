import asyncio
import unittest
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.schemas.monitoring import ModelStabilityStatus, RolloutStatus
from app.schemas.trading import TradeRequest
from app.services.alpha_engine import AlphaEngine
from app.services.allocation_engine import AllocationEngine
from app.services.drawdown_protection import DrawdownProtectionService
from app.services.execution_queue_manager import ExecutionQueueManager
from app.services.latency_monitor import LatencyMonitor
from app.services.liquidity_monitor import LiquidityMonitor
from app.services.micro_mode_controller import MicroModeController
from app.services.multi_chain_router import MultiChainRouter
from app.services.paper_execution import PaperExecutionEngine
from app.services.performance_tracker import PerformanceTracker
from app.services.redis_state_manager import RedisStateManager
from app.services.security_scanner import SecurityScanner
from app.services.sentiment_engine import SentimentEngine
from app.services.shard_manager import ShardManager
from app.services.signal_broadcaster import SignalBroadcaster
from app.services.system_monitor import SystemMonitorService
from app.services.tax_engine import TaxEngine
from app.services.trading_orchestrator import TradingOrchestrator
from app.services.virtual_order_manager import VirtualOrderManager
from app.services.whale_tracker import WhaleTracker


class InMemoryCache:
    def __init__(self):
        self.store = {}

    def get_json(self, key):
        return self.store.get(key)

    def set_json(self, key, value, ttl):
        self.store[key] = value

    def increment(self, key, ttl):
        self.store[key] = int(self.store.get(key, 0)) + 1
        return self.store[key]

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ttl=None):
        self.store[key] = value

    def set_if_absent(self, key, value, ttl):
        if key in self.store:
            return False
        self.store[key] = value
        return True

    def delete(self, key):
        self.store.pop(key, None)

    def publish(self, channel, message):
        self.store[f"pub:{channel}"] = message
        return 1

    def keys(self, pattern):
        prefix = pattern.replace("*", "")
        return [key for key in self.store if key.startswith(prefix)]

    def zadd_json(self, key, score, value):
        self.store.setdefault(key, []).append((score, value))

    def zpop_due_json(self, key, max_score, limit=100):
        entries = sorted(self.store.get(key, []), key=lambda item: item[0])
        due_entries = [(score, value) for score, value in entries if score <= max_score]
        due = [value for _, value in due_entries[:limit]]
        self.store[key] = due_entries[limit:] + [(score, value) for score, value in entries if score > max_score]
        return due

    def zcard(self, key):
        return len(self.store.get(key, []))


class StubMarketData:
    async def fetch_latest_price(self, symbol: str) -> float:
        return 100.0

    async def fetch_order_book(self, symbol: str) -> dict:
        return {
            "bids": [{"price": 99.9, "qty": 10.0}],
            "asks": [{"price": 100.1, "qty": 10.0}],
        }


class StubFirestore:
    def __init__(self):
        self.trades = []
        self.samples = []
        self.tax_records = []

    def save_trade(self, payload):
        self.trades.append(payload)
        return payload["trade_id"]

    def load_trade_by_signal_id(self, signal_id):
        for trade in self.trades:
            if trade.get("signal_id") == signal_id:
                return trade
        return None

    def save_training_sample(self, payload):
        self.samples.append(payload)
        return payload["trade_id"]

    def save_tax_record(self, payload):
        self.tax_records.append(payload)
        return payload["trade_id"]

    def save_performance_snapshot(self, user_id, payload):
        return None


class StubRolloutManager:
    def status(self):
        return RolloutStatus(stage_index=1, stage_name="MICRO", capital_fraction=0.01, mode="paper", eligible_for_upgrade=False, downgrade_flag=False)


class StubModelStability:
    def record_live_outcome(self, won: bool):
        return ModelStabilityStatus(
            active_model_version="v1",
            fallback_model_version=None,
            live_win_rate=0.5,
            training_win_rate=0.6,
            drift_score=0.0,
            degraded=False,
        )


class VirtualOrderManagerTest(unittest.TestCase):
    def test_stages_and_flushes_aggregate_order_with_proportional_allocations(self):
        cache = InMemoryCache()
        settings = Settings(
            trading_mode="paper",
            redis_url="redis://unused",
            default_portfolio_balance=10_000,
        )
        market_data = StubMarketData()
        firestore = StubFirestore()
        allocation_engine = AllocationEngine(precision=settings.virtual_order_precision)
        virtual_order_manager = VirtualOrderManager(settings, cache, allocation_engine)
        shard_manager = ShardManager(settings)
        execution_queue_manager = ExecutionQueueManager(settings, cache, shard_manager)
        signal_broadcaster = SignalBroadcaster(settings, cache, execution_queue_manager)
        orchestrator = TradingOrchestrator(
            settings=settings,
            market_data=market_data,
            feature_pipeline=None,
            ai_engine=None,
            strategy_engine=None,
            risk_engine=None,
            execution_engine=None,
            paper_execution_engine=PaperExecutionEngine(settings, market_data),
            cache=cache,
            drawdown_protection=DrawdownProtectionService(settings, cache),
            system_monitor=SystemMonitorService(settings, cache),
            rollout_manager=StubRolloutManager(),
            model_stability=StubModelStability(),
            alpha_engine=AlphaEngine(),
            micro_mode_controller=MicroModeController(settings, cache),
            whale_tracker=WhaleTracker.create_default(),
            liquidity_monitor=LiquidityMonitor(),
            sentiment_engine=SentimentEngine(),
            security_scanner=SecurityScanner(),
            multi_chain_router=MultiChainRouter(settings),
            tax_engine=TaxEngine(),
            redis_state_manager=RedisStateManager(settings, cache),
            performance_tracker=PerformanceTracker(cache, firestore),
            firestore=firestore,
            virtual_order_manager=virtual_order_manager,
            shard_manager=shard_manager,
            execution_queue_manager=execution_queue_manager,
            signal_broadcaster=signal_broadcaster,
            latency_monitor=LatencyMonitor(settings, cache),
        )

        first = asyncio.run(
            orchestrator.submit_virtual_order(
                TradeRequest(
                    user_id="u1",
                    symbol="BTCUSDT",
                    side="BUY",
                    order_type="MARKET",
                    confidence=0.8,
                    reason="alpha-1",
                    quantity=1.0,
                )
            )
        )
        second = asyncio.run(
            orchestrator.submit_virtual_order(
                TradeRequest(
                    user_id="u2",
                    symbol="BTCUSDT",
                    side="BUY",
                    order_type="MARKET",
                    confidence=0.7,
                    reason="alpha-2",
                    quantity=2.0,
                )
            )
        )

        self.assertEqual(first["status"], "PENDING_AGGREGATION")
        self.assertEqual(second["intent_count"], 2)

        flushed = asyncio.run(orchestrator.flush_virtual_orders("BTCUSDT", "BUY"))

        self.assertEqual(len(flushed), 1)
        aggregate = flushed[0]["aggregate"]
        self.assertEqual(aggregate["allocation_count"], 2)
        self.assertEqual(len(firestore.trades), 2)
        allocated_total = sum(item["allocated_quantity"] for item in flushed[0]["allocations"])
        self.assertGreater(allocated_total, 0.0)
        self.assertAlmostEqual(
            allocated_total,
            aggregate["executed_quantity"],
            places=6,
        )
        self.assertGreater(
            flushed[0]["allocations"][1]["allocated_quantity"],
            flushed[0]["allocations"][0]["allocated_quantity"],
        )


if __name__ == "__main__":
    unittest.main()
