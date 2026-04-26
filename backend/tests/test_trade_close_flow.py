import asyncio
import unittest
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.core.exceptions import StateError
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
from app.services.portfolio_ledger import PortfolioLedgerService
from app.services.redis_state_manager import RedisStateManager
from app.services.risk_engine import RiskEngine
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

    def delete_if_value_matches(self, key, expected_value):
        if self.store.get(key) == expected_value:
            self.store.pop(key, None)
            return True
        return False

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
    def latest_stream_price(self, symbol: str):
        return None

    async def fetch_latest_price(self, symbol: str) -> float:
        return 100.0

    async def fetch_order_book(self, symbol: str) -> dict:
        return {
            "bids": [{"price": 99.9, "qty": 10.0}],
            "asks": [{"price": 100.1, "qty": 10.0}],
        }


class StubExecutionEngine:
    def fetch_order_status(self, symbol: str, order_id: int) -> dict:
        return {"status": "FILLED", "origQty": "10", "executedQty": "10"}


class StubFirestore:
    def __init__(self):
        self.updated_trades = []
        self.micro = []
        self.public_trades = []

    def save_signal(self, payload):
        return payload.get("signal_id", "signal")

    def save_trade(self, payload):
        return payload["trade_id"]

    def load_trade_by_signal_id(self, signal_id):
        return None

    def save_training_sample(self, payload):
        return payload.get("trade_id", "sample")

    def update_trade(self, trade_id, payload):
        self.updated_trades.append((trade_id, payload))

    def save_tax_record(self, payload):
        return payload.get("trade_id", "tax")

    def save_performance_snapshot(self, user_id, payload):
        return None

    def save_micro_performance(self, payload):
        self.micro.append(payload)

    def publish_trade_to_public_log(self, trade):
        self.public_trades.append(trade)
        return trade.get("trade_id", "public")


class StubRolloutManager:
    def status(self):
        return RolloutStatus(stage_index=3, stage_name="EXPANDED", capital_fraction=1.0, mode="paper", eligible_for_upgrade=False, downgrade_flag=False)

    def record_performance(self, win_rate: float, profit_factor: float, trades: int, drawdown: float = 0.0):
        return self.status()


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


class TradeCloseFlowTest(unittest.TestCase):
    def _build_orchestrator(self):
        cache = InMemoryCache()
        settings = Settings(
            trading_mode="paper",
            redis_url="redis://unused",
            model_dir=str(Path.cwd() / "tmp-artifacts-close-tests"),
            default_portfolio_balance=10_000,
        )
        market_data = StubMarketData()
        firestore = StubFirestore()
        drawdown = DrawdownProtectionService(settings, cache)
        monitor = SystemMonitorService(settings, cache)
        paper = PaperExecutionEngine(settings, market_data)
        allocation_engine = AllocationEngine(precision=settings.virtual_order_precision)
        virtual_order_manager = VirtualOrderManager(settings, cache, allocation_engine)
        shard_manager = ShardManager(settings)
        execution_queue_manager = ExecutionQueueManager(settings, cache, shard_manager)
        signal_broadcaster = SignalBroadcaster(settings, cache, execution_queue_manager)
        redis_state_manager = RedisStateManager(settings, cache)
        orchestrator = TradingOrchestrator(
            settings=settings,
            market_data=market_data,
            feature_pipeline=None,
            ai_engine=None,
            strategy_engine=None,
            risk_engine=RiskEngine(settings),
            execution_engine=StubExecutionEngine(),
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
            redis_state_manager=redis_state_manager,
            performance_tracker=PerformanceTracker(cache, firestore),
            firestore=firestore,
            virtual_order_manager=virtual_order_manager,
            shard_manager=shard_manager,
            execution_queue_manager=execution_queue_manager,
            signal_broadcaster=signal_broadcaster,
            portfolio_ledger=PortfolioLedgerService(settings, cache, market_data, redis_state_manager, firestore),
            latency_monitor=LatencyMonitor(settings, cache),
        )
        return orchestrator, firestore

    def test_partial_close_preserves_remaining_quantity_and_books_realized_pnl(self):
        orchestrator, firestore = self._build_orchestrator()
        opened = asyncio.run(
            orchestrator.execute_signal(
                TradeRequest(
                    user_id="u1",
                    symbol="BTCUSDT",
                    side="BUY",
                    order_type="MARKET",
                    confidence=0.8,
                    reason="open",
                    requested_notional=100.0,
                    expected_return=0.01,
                    feature_snapshot={"15m_volume": 500000.0},
                )
            )
        )

        partial = orchestrator.close_trade_position(
            user_id="u1",
            trade_id=opened.trade_id,
            exit_price=110.0,
            closed_quantity=0.5,
            exit_fee=0.1,
            reason="trim",
        )

        self.assertEqual(partial.status, "PARTIAL")
        self.assertAlmostEqual(partial.closed_quantity, 0.5, places=6)
        self.assertAlmostEqual(partial.remaining_quantity, 0.5, places=6)
        self.assertGreater(partial.realized_pnl, 4.69)

        active = orchestrator.redis_state_manager.load_active_trade(opened.trade_id)
        self.assertIsNotNone(active)
        self.assertAlmostEqual(active["executed_quantity"], 0.5, places=6)

        final = orchestrator.close_trade_position(
            user_id="u1",
            trade_id=opened.trade_id,
            exit_price=120.0,
            exit_fee=0.1,
            reason="exit_all",
        )

        self.assertEqual(final.status, "CLOSED")
        self.assertAlmostEqual(final.remaining_quantity, 0.0, places=6)
        self.assertIsNone(orchestrator.redis_state_manager.load_active_trade(opened.trade_id))
        self.assertTrue(any(payload.get("status") == "CLOSED" for _, payload in firestore.updated_trades))
        self.assertEqual(len(firestore.public_trades), 1)
        self.assertEqual(firestore.public_trades[0]["trade_id"], opened.trade_id)
        self.assertNotIn("user_id", firestore.public_trades[0])

        with self.assertRaises(StateError) as ctx:
            orchestrator.close_trade_position(
                user_id="u1",
                trade_id=opened.trade_id,
                exit_price=120.0,
                exit_fee=0.1,
                reason="duplicate_close",
            )

        self.assertEqual(ctx.exception.error_code, "TRADE_ALREADY_CLOSED")

    def test_startup_reconciliation_routes_filled_trade_through_close_flow(self):
        orchestrator, firestore = self._build_orchestrator()
        orchestrator.execution_engine.fetch_order_status = lambda symbol, order_id: {
            "status": "FILLED",
            "origQty": "1",
            "executedQty": "1",
            "cummulativeQuoteQty": "120.0",
            "feePaid": 0.25,
        }
        orchestrator.redis_state_manager.save_active_trade(
            "trade-reconcile-1",
            {
                "trade_id": "trade-reconcile-1",
                "user_id": "u1",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "status": "SUBMITTED",
                "order_id": "101",
                "entry": 100.0,
                "executed_quantity": 1.0,
                "notional": 100.0,
                "fees": 0.1,
            },
        )

        reconciled = orchestrator.reconcile_startup_state()

        self.assertEqual(reconciled[0]["action"], "close_reconciled")
        self.assertIsNone(orchestrator.redis_state_manager.load_active_trade("trade-reconcile-1"))
        self.assertTrue(any(payload.get("status") == "CLOSED" for _, payload in firestore.updated_trades))
        self.assertTrue(any(payload.get("profit") is not None for _, payload in firestore.updated_trades))
