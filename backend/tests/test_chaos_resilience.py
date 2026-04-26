import asyncio
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

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
from app.services.risk_engine import RiskEngine
from app.services.security_scanner import SecurityScanner
from app.services.sentiment_engine import SentimentEngine
from app.services.shard_manager import ShardManager
from app.services.signal_broadcaster import SignalBroadcaster
from app.services.signal_websocket_manager import SignalWebSocketManager
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


class FailingPublishCache(InMemoryCache):
    def __init__(self, failing_channels):
        super().__init__()
        self.failing_channels = set(failing_channels)
        self.publish_attempts = {}

    def publish(self, channel, message):
        self.publish_attempts[channel] = self.publish_attempts.get(channel, 0) + 1
        if channel in self.failing_channels:
            raise ConnectionError(f"{channel} unavailable")
        return super().publish(channel, message)


class StubMarketData:
    def __init__(self, latest_price=100.0, order_book=None):
        self.latest_price = latest_price
        self.order_book = order_book or {
            "bids": [{"price": 99.9, "qty": 10.0}],
            "asks": [{"price": 100.1, "qty": 10.0}],
        }

    async def fetch_latest_price(self, symbol: str) -> float:
        return self.latest_price

    async def fetch_order_book(self, symbol: str) -> dict:
        return self.order_book


class FlakyExecutionEngine:
    def __init__(self):
        self.calls = 0

    def place_order(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("exchange api unavailable")
        quantity = float(kwargs["quantity"])
        return {
            "orderId": "live-order-1",
            "status": "FILLED",
            "price": "100.00000000",
            "executedQty": f"{quantity:.8f}",
            "origQty": f"{quantity:.8f}",
            "fills": [{"price": "100.00000000", "qty": f"{quantity:.8f}"}],
            "feePaid": 0.1,
            "slippageBps": 10.0,
            "executionLatencyMs": 12.0,
            "filledRatio": 1.0,
        }

    def fetch_order_status(self, symbol: str, order_id: int) -> dict:
        return {"status": "FILLED", "origQty": "1", "executedQty": "1"}


class StableExecutionEngine:
    def __init__(self):
        self.calls = 0

    def place_order(self, **kwargs):
        self.calls += 1
        quantity = float(kwargs["quantity"])
        return {
            "orderId": "live-order-1",
            "status": "FILLED",
            "price": "100.00000000",
            "executedQty": f"{quantity:.8f}",
            "origQty": f"{quantity:.8f}",
            "fills": [{"price": "100.00000000", "qty": f"{quantity:.8f}"}],
            "feePaid": 0.1,
            "slippageBps": 10.0,
            "executionLatencyMs": 12.0,
            "filledRatio": 1.0,
        }

    def fetch_order_status(self, symbol: str, order_id: int) -> dict:
        return {"status": "FILLED", "origQty": "1", "executedQty": "1"}


class StubFirestore:
    def __init__(self):
        self.trades = []
        self.samples = []

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
        return payload["trade_id"]

    def save_performance_snapshot(self, user_id, payload):
        return None


class FailingAfterOrderFirestore(StubFirestore):
    def save_trade(self, payload):
        raise RuntimeError("firestore write failed after order submission")


class StubRolloutManager:
    def status(self):
        return RolloutStatus(
            stage_index=1,
            stage_name="MICRO",
            capital_fraction=0.01,
            mode="live",
            eligible_for_upgrade=False,
            downgrade_flag=False,
        )


class StubModelStability:
    def load_status(self):
        return ModelStabilityStatus(
            active_model_version="v1",
            fallback_model_version=None,
            live_win_rate=0.6,
            training_win_rate=0.6,
            drift_score=0.0,
            degraded=False,
        )

    def record_live_outcome(self, won: bool):
        return self.load_status()


class FakeWebSocket:
    def __init__(self, *, fail_once=False):
        self.fail_once = fail_once
        self.accepted = False
        self.messages = []
        self._failed = False

    async def accept(self):
        self.accepted = True

    async def send_text(self, message):
        if self.fail_once and not self._failed:
            self._failed = True
            raise RuntimeError("socket dropped")
        self.messages.append(json.loads(message))


class FailingPubSub:
    def subscribe(self, channel):
        return None

    def get_message(self, timeout=1.0):
        raise ConnectionError("redis unavailable")

    def close(self):
        return None


class RecoveringPubSub:
    def __init__(self, manager: SignalWebSocketManager):
        self.manager = manager
        self.sent = False

    def subscribe(self, channel):
        return None

    def get_message(self, timeout=1.0):
        if self.sent:
            return None
        self.sent = True
        self.manager._listener_stop.set()
        return {
            "type": "message",
            "data": json.dumps({"type": "signal", "symbol": "BTCUSDT", "signal_version": 11}),
        }

    def close(self):
        return None


class FakeRedisClient:
    def __init__(self, pubsub):
        self._pubsub = pubsub
        self.closed = False

    def pubsub(self, ignore_subscribe_messages=True):
        return self._pubsub

    def close(self):
        self.closed = True


class ChaosResilienceTest(unittest.TestCase):
    def _build_orchestrator(self, *, trading_mode="paper", cache=None, execution_engine=None, firestore=None):
        cache = cache or InMemoryCache()
        settings = Settings(
            trading_mode=trading_mode,
            redis_url="redis://unused",
            model_dir=str(Path.cwd() / "tmp-artifacts-tests"),
            default_portfolio_balance=10_000,
            websocket_redis_reconnect_seconds=0.01,
            randomized_execution_delay_min_ms=0,
            randomized_execution_delay_max_ms=0,
            delayed_queue_min_ms=0,
            delayed_queue_max_ms=0,
        )
        market_data = StubMarketData()
        firestore = firestore or StubFirestore()
        drawdown = DrawdownProtectionService(settings, cache)
        monitor = SystemMonitorService(settings, cache)
        paper = PaperExecutionEngine(settings, market_data)
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
            risk_engine=RiskEngine(settings),
            execution_engine=execution_engine or FlakyExecutionEngine(),
            paper_execution_engine=paper,
            cache=cache,
            drawdown_protection=drawdown,
            system_monitor=monitor,
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
        return orchestrator, firestore, cache, signal_broadcaster, execution_queue_manager

    def test_exchange_api_failure_recovers_without_trade_loss_or_duplication(self):
        orchestrator, firestore, cache, _, _ = self._build_orchestrator(trading_mode="live")
        request = TradeRequest(
            user_id="u1",
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            confidence=0.81,
            reason="chaos exchange failure",
            requested_notional=100.0,
            signal_id="chaos-signal-1",
            feature_snapshot={"15m_volume": 500000.0, "volatility": 0.01},
        )

        with self.assertRaisesRegex(RuntimeError, "exchange api unavailable"):
            asyncio.run(orchestrator.execute_signal(request))

        self.assertEqual(len(firestore.trades), 0)
        self.assertEqual(orchestrator.redis_state_manager.restore_active_trades(), [])
        self.assertIsNone(cache.get(f"signal:response:{request.signal_id}"))

        recovered = asyncio.run(orchestrator.execute_signal(request))
        duplicate = asyncio.run(orchestrator.execute_signal(request))

        self.assertEqual(recovered.trade_id, "live-order-1")
        self.assertFalse(recovered.duplicate_signal)
        self.assertTrue(duplicate.duplicate_signal)
        self.assertEqual(len(firestore.trades), 1)
        self.assertEqual(len(firestore.samples), 1)

    def test_post_submission_failure_still_deduplicates_signal_retries(self):
        firestore = FailingAfterOrderFirestore()
        execution_engine = StableExecutionEngine()
        orchestrator, _, cache, _, _ = self._build_orchestrator(
            trading_mode="live",
            firestore=firestore,
            execution_engine=execution_engine,
        )
        request = TradeRequest(
            user_id="u1",
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            confidence=0.81,
            reason="chaos mid-write failure",
            requested_notional=100.0,
            signal_id="chaos-signal-2",
            feature_snapshot={"15m_volume": 500000.0, "volatility": 0.01},
        )

        with self.assertRaisesRegex(RuntimeError, "firestore write failed after order submission"):
            asyncio.run(orchestrator.execute_signal(request))

        opening_trade = orchestrator.redis_state_manager.load_active_trade("live-order-1")
        self.assertIsNotNone(opening_trade)
        self.assertEqual(opening_trade["status"], "OPENING")
        self.assertEqual(
            orchestrator.redis_state_manager.load_signal_trade(request.signal_id),
            "live-order-1",
        )
        duplicate = asyncio.run(orchestrator.execute_signal(request))

        self.assertEqual(duplicate.trade_id, "live-order-1")
        self.assertTrue(duplicate.duplicate_signal)
        self.assertIsNotNone(cache.get(f"signal:response:{request.signal_id}"))
        self.assertEqual(execution_engine.calls, 1)

    def test_redis_disconnection_does_not_drop_or_duplicate_fanout_jobs(self):
        cache = FailingPublishCache({"signals:central", "signals:fanout"})
        _, _, _, broadcaster, queue_manager = self._build_orchestrator(cache=cache)
        broadcaster.register_subscription("u1", tier="pro", balance=1000.0, risk_profile="moderate")

        with patch("app.services.signal_broadcaster.logger.warning") as warning_log:
            published = broadcaster.publish_signal(
                {
                    "signal_id": "chaos-redis-1",
                    "symbol": "BTCUSDT",
                    "strategy": "BREAKOUT",
                    "alpha_decision": {"final_score": 85.0},
                    "required_tier": "free",
                    "min_balance": 0.0,
                    "allowed_risk_profiles": ["moderate"],
                }
            )

        queued = []
        for shard_id in range(broadcaster.settings.execution_shard_count):
            queued.extend(queue_manager.dequeue_batch(shard_id, limit=10))

        self.assertEqual(published["distribution"]["queued_total"], 1)
        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0]["signal_id"], "chaos-redis-1")
        self.assertEqual(cache.publish_attempts["signals:central"], 1)
        self.assertEqual(cache.publish_attempts["signals:fanout"], 1)
        self.assertGreaterEqual(warning_log.call_count, 2)

    def test_websocket_drop_and_redis_reconnect_recover_cleanly(self):
        settings = Settings(
            redis_url="redis://unused",
            websocket_redis_reconnect_seconds=0.01,
        )
        manager = SignalWebSocketManager(settings)
        dropped = FakeWebSocket(fail_once=True)
        healthy = FakeWebSocket()
        replacement = FakeWebSocket()

        asyncio.run(manager.connect(dropped, "alice"))
        asyncio.run(manager.connect(healthy, "bob"))
        asyncio.run(manager.broadcast({"type": "signal", "signal_version": 1}))
        asyncio.run(manager.connect(replacement, "alice"))
        asyncio.run(manager.broadcast({"type": "signal", "signal_version": 2}))

        self.assertEqual(healthy.messages, [{"type": "signal", "signal_version": 1}, {"type": "signal", "signal_version": 2}])
        self.assertEqual(replacement.messages, [{"type": "signal", "signal_version": 2}])
        self.assertEqual(dropped.messages, [])

        received = []

        async def capture_broadcast(payload):
            received.append(payload)

        failing_client = FakeRedisClient(FailingPubSub())
        recovering_client = FakeRedisClient(RecoveringPubSub(manager))
        with patch.object(manager, "broadcast", side_effect=capture_broadcast), patch(
            "app.services.signal_websocket_manager.Redis.from_url",
            side_effect=[failing_client, recovering_client],
        ) as redis_factory, patch(
            "app.services.signal_websocket_manager.asyncio.run_coroutine_threadsafe",
            side_effect=lambda coro, loop: asyncio.run(coro),
        ), patch("app.services.signal_websocket_manager.logger.warning"):
            manager._listener_stop.clear()
            manager._loop = object()
            manager._listen_for_signals()

        self.assertEqual(redis_factory.call_count, 2)
        self.assertEqual(received, [{"type": "signal", "symbol": "BTCUSDT", "signal_version": 11}])


if __name__ == "__main__":
    unittest.main()
