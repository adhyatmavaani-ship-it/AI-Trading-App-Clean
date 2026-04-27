import asyncio
import unittest
import sys
from pathlib import Path
import time
from unittest.mock import patch

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.schemas.monitoring import ModelStabilityStatus, RolloutStatus
from app.schemas.trading import AlphaContext, AlphaDecision, SentimentContext, TradeRequest, WhaleContext
from app.services.alpha_engine import AlphaEngine
from app.services.allocation_engine import AllocationEngine
from app.services.drawdown_protection import DrawdownProtectionService
from app.services.execution_queue_manager import ExecutionQueueManager
from app.services.latency_monitor import LatencyMonitor
from app.services.liquidity_monitor import LiquidityMonitor
from app.services.meta_controller import MetaController
from app.services.micro_mode_controller import MicroModeController
from app.services.multi_chain_router import MultiChainRouter
from app.services.paper_execution import PaperExecutionEngine
from app.services.performance_tracker import PerformanceTracker
from app.services.portfolio_manager import PortfolioManager
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
        remaining = due_entries[limit:] + [(score, value) for score, value in entries if score > max_score]
        self.store[key] = remaining
        return due

    def zcard(self, key):
        return len(self.store.get(key, []))


class StubMarketData:
    def __init__(self, *, latest_price: float = 100.0, order_book: dict | None = None):
        self.latest_price = latest_price
        self.order_book = order_book or {
            "bids": [{"price": 99.9, "qty": 10.0}, {"price": 99.8, "qty": 12.0}],
            "asks": [{"price": 100.1, "qty": 10.0}, {"price": 100.2, "qty": 12.0}],
        }
        trend_up = [100 + (index * 0.5) for index in range(40)]
        trend_up_peer = [value * 0.5 for value in trend_up]
        trend_down = [40 - (index * 0.2) for index in range(40)]
        self.ohlcv = {
            "BTCUSDT": pd.DataFrame({"close": trend_up}),
            "ETHUSDT": pd.DataFrame({"close": trend_up_peer}),
            "SOLUSDT": pd.DataFrame({"close": trend_down}),
        }

    async def fetch_latest_price(self, symbol: str) -> float:
        return self.latest_price

    async def fetch_order_book(self, symbol: str) -> dict:
        return self.order_book

    async def fetch_multi_timeframe_ohlcv(self, symbol: str, intervals=("15m",)) -> dict:
        return {"15m": self.ohlcv[symbol]}


class StubExecutionEngine:
    def fetch_order_status(self, symbol: str, order_id: int) -> dict:
        return {"status": "PARTIALLY_FILLED", "origQty": "10", "executedQty": "4"}


class StubFirestore:
    def __init__(self):
        self.trades = []
        self.samples = []
        self.tax_records = []
        self.signals = []

    def save_trade(self, payload):
        self.trades.append(payload)
        return payload["trade_id"]

    def load_trade_by_signal_id(self, signal_id):
        for trade in self.trades:
            if trade.get("signal_id") == signal_id:
                return trade
        return None

    def save_signal(self, payload):
        self.signals.append(payload)
        return payload.get("signal_id", "signal")

    def save_training_sample(self, payload):
        self.samples.append(payload)
        return payload["trade_id"]

    def update_trade(self, trade_id, payload):
        return None

    def save_tax_record(self, payload):
        self.tax_records.append(payload)
        return payload.get("trade_id", "tax")

    def save_performance_snapshot(self, user_id, payload):
        return None


class StubRolloutManager:
    def status(self):
        return RolloutStatus(stage_index=1, stage_name="MICRO", capital_fraction=0.01, mode="paper", eligible_for_upgrade=False, downgrade_flag=False)

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
        return ModelStabilityStatus(
            active_model_version="v1",
            fallback_model_version=None,
            live_win_rate=1.0 if won else 0.0,
            training_win_rate=0.6,
            drift_score=0.0,
            degraded=False,
        )


class TradingOrchestratorReliabilityTest(unittest.TestCase):
    def _build_orchestrator(self, *, market_data: StubMarketData | None = None):
        cache = InMemoryCache()
        settings = Settings(
            trading_mode="paper",
            redis_url="redis://unused",
            model_dir=str(Path.cwd() / "tmp-artifacts-tests"),
            default_portfolio_balance=10_000,
        )
        market_data = market_data or StubMarketData()
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
        portfolio_ledger = PortfolioLedgerService(settings, cache, market_data, redis_state_manager, firestore)
        portfolio_manager = PortfolioManager(settings)
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
            portfolio_ledger=portfolio_ledger,
            portfolio_manager=portfolio_manager,
            virtual_order_manager=virtual_order_manager,
            shard_manager=shard_manager,
            execution_queue_manager=execution_queue_manager,
            signal_broadcaster=signal_broadcaster,
            latency_monitor=LatencyMonitor(settings, cache),
        )
        return orchestrator, firestore

    def test_duplicate_signals_do_not_create_duplicate_trades(self):
        orchestrator, firestore = self._build_orchestrator()
        request = TradeRequest(
            user_id="u1",
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            confidence=0.8,
            reason="test",
            requested_notional=100.0,
            signal_id="signal-1",
        )

        first = asyncio.run(orchestrator.execute_signal(request))
        second = asyncio.run(orchestrator.execute_signal(request))

        self.assertFalse(first.duplicate_signal)
        self.assertTrue(second.duplicate_signal)
        self.assertEqual(len(firestore.trades), 1)

    def test_duplicate_signal_recovers_existing_trade_from_firestore_when_cache_is_missing(self):
        orchestrator, firestore = self._build_orchestrator()
        request = TradeRequest(
            user_id="u1",
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            confidence=0.8,
            reason="test",
            requested_notional=100.0,
            signal_id="signal-recover-1",
        )

        first = asyncio.run(orchestrator.execute_signal(request))
        orchestrator.cache.delete(f"signal:response:{request.signal_id}")

        duplicate = asyncio.run(orchestrator.execute_signal(request))

        self.assertEqual(duplicate.trade_id, first.trade_id)
        self.assertTrue(duplicate.duplicate_signal)
        self.assertEqual(len(firestore.trades), 1)

    def test_duplicate_signal_recovers_existing_trade_from_opening_state(self):
        orchestrator, _ = self._build_orchestrator()
        signal_id = "signal-opening-1"
        orchestrator.redis_state_manager.remember_signal_trade(signal_id, "order-1")
        orchestrator.redis_state_manager.save_active_trade(
            "order-1",
            {
                "trade_id": "order-1",
                "order_id": "order-1",
                "signal_id": signal_id,
                "user_id": "u1",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "status": "OPENING",
                "submitted_state": "OPENING",
                "requested_quantity": 1.0,
                "executed_quantity": 1.0,
            },
        )
        request = TradeRequest(
            user_id="u1",
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            confidence=0.8,
            reason="recover opening",
            quantity=1.0,
            signal_id=signal_id,
        )

        duplicate = asyncio.run(orchestrator.execute_signal(request))

        self.assertEqual(duplicate.trade_id, "order-1")
        self.assertEqual(duplicate.status, "OPENING")
        self.assertTrue(duplicate.duplicate_signal)

    def test_bearish_macro_bias_halves_position_size(self):
        orchestrator, firestore = self._build_orchestrator()
        orchestrator.cache.set_json(
            "macro:global_bias",
            {
                "regime": "BEARISH",
                "multiplier": 0.5,
                "reason": "Nasdaq lead-lag stress",
            },
            ttl=3600,
        )
        request = TradeRequest(
            user_id="u1",
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            confidence=0.8,
            reason="macro test",
            requested_notional=100.0,
            expected_return=0.01,
            feature_snapshot={"15m_volume": 500000.0},
        )

        response = asyncio.run(orchestrator.execute_signal(request))
        self.assertEqual(response.macro_bias_regime, "BEARISH")
        self.assertAlmostEqual(response.macro_bias_multiplier, 0.5, places=4)
        saved_trade = firestore.trades[-1]
        self.assertAlmostEqual(saved_trade["macro_bias_multiplier"], 0.5, places=4)
        self.assertLess(saved_trade["entry"] - response.stop_loss, 0.6)

    def test_trade_recorded_uses_debug_logging_in_paper_mode(self):
        orchestrator, _ = self._build_orchestrator()

        with patch("app.services.trading_orchestrator.logger.debug") as debug_log, patch(
            "app.services.trading_orchestrator.logger.info"
        ) as info_log:
            orchestrator._log_trade_recorded(
                trade_id="trade-1",
                symbol="BTCUSDT",
                side="BUY",
            )

        debug_log.assert_called_once()
        info_log.assert_not_called()
        self.assertEqual(debug_log.call_args.args[0], "trade_recorded")
        self.assertEqual(
            debug_log.call_args.kwargs["extra"]["context"]["trading_mode"],
            "paper",
        )

    def test_meta_controller_blocks_trade_when_trade_limit_is_hit(self):
        orchestrator, _ = self._build_orchestrator()
        orchestrator.meta_controller = MetaController(
            settings=orchestrator.settings,
            cache=orchestrator.cache,
            system_monitor=orchestrator.system_monitor,
            drawdown_protection=orchestrator.drawdown_protection,
            risk_engine=RiskEngine(orchestrator.settings),
            rollout_manager=orchestrator.rollout_manager,
            model_stability=orchestrator.model_stability,
            redis_state_manager=orchestrator.redis_state_manager,
        )
        current_hour_key = orchestrator.meta_controller._trade_count_key("u1")
        orchestrator.cache.set(
            current_hour_key,
            str(orchestrator.settings.meta_max_trades_per_hour),
            ttl=3600,
        )
        request = TradeRequest(
            user_id="u1",
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            confidence=0.8,
            reason="meta limit test",
            requested_notional=100.0,
            expected_return=0.01,
            feature_snapshot={"15m_volume": 500000.0, "volatility": 0.01},
        )

        with self.assertRaisesRegex(ValueError, "Meta controller blocked trade"):
            asyncio.run(orchestrator.execute_signal(request))

    def test_meta_decision_log_is_written_for_approved_trade(self):
        orchestrator, _ = self._build_orchestrator()
        orchestrator.meta_controller = MetaController(
            settings=orchestrator.settings,
            cache=orchestrator.cache,
            system_monitor=orchestrator.system_monitor,
            drawdown_protection=orchestrator.drawdown_protection,
            risk_engine=RiskEngine(orchestrator.settings),
            rollout_manager=orchestrator.rollout_manager,
            model_stability=orchestrator.model_stability,
            redis_state_manager=orchestrator.redis_state_manager,
        )
        request = TradeRequest(
            user_id="u1",
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            confidence=0.8,
            reason="meta log test",
            requested_notional=100.0,
            expected_return=0.01,
            feature_snapshot={"15m_volume": 500000.0, "volatility": 0.01},
            strategy="AI",
            alpha_context=AlphaContext(
                whale=WhaleContext(score=0.82, accumulation_score=0.8, summary="Strong accumulation"),
                sentiment=SentimentContext(hype_score=0.74, narrative="bullish"),
            ),
            alpha_decision=AlphaDecision(final_score=84.0, allow_trade=True),
        )

        response = asyncio.run(orchestrator.execute_signal(request))
        payload = orchestrator.meta_controller.get_decision_log(response.trade_id)

        self.assertIsNotNone(payload)
        self.assertEqual(payload["decision"], "APPROVED")
        self.assertEqual(payload["symbol"], "BTCUSDT")

    def test_portfolio_controls_reduce_correlated_trade_size(self):
        orchestrator, firestore = self._build_orchestrator()
        existing_trade = {
            "trade_id": "open-1",
            "user_id": "u1",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "entry": 100.0,
            "executed_quantity": 20.0,
            "notional": 2000.0,
            "fees": 0.0,
        }
        orchestrator.redis_state_manager.save_active_trade("open-1", existing_trade)
        if orchestrator.portfolio_ledger is not None:
            orchestrator.portfolio_ledger.record_trade_open(
                user_id="u1",
                trade_id="open-1",
                symbol="BTCUSDT",
                side="BUY",
                entry_price=100.0,
                executed_quantity=20.0,
                notional=2000.0,
                fee_paid=0.0,
            )
        request = TradeRequest(
            user_id="u1",
            symbol="ETHUSDT",
            side="BUY",
            order_type="MARKET",
            confidence=0.8,
            reason="portfolio risk test",
            requested_notional=5000.0,
            expected_return=0.01,
            feature_snapshot={"15m_volume": 500000.0, "volatility": 0.01, "15m_return": 0.03},
        )

        response = asyncio.run(orchestrator.execute_signal(request))
        saved_trade = firestore.trades[-1]

        self.assertLess(saved_trade["requested_notional"], 5000.0)
        self.assertGreater(response.executed_quantity, 0.0)
        self.assertGreater(saved_trade["risk_fraction"], 0.0)

    def test_strict_confidence_floor_blocks_trade(self):
        orchestrator, _ = self._build_orchestrator()
        request = TradeRequest(
            user_id="u1",
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            confidence=0.65,
            reason="confidence floor test",
            requested_notional=100.0,
        )

        with self.assertRaisesRegex(ValueError, "confidence"):
            asyncio.run(orchestrator.execute_signal(request))

    def test_duplicate_symbol_trade_is_blocked(self):
        orchestrator, _ = self._build_orchestrator()
        orchestrator.redis_state_manager.save_active_trade(
            "open-btc",
            {
                "trade_id": "open-btc",
                "user_id": "u1",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "entry": 100.0,
                "executed_quantity": 10.0,
                "notional": 1000.0,
                "fees": 0.0,
            },
        )
        orchestrator.portfolio_ledger.record_trade_open(
            user_id="u1",
            trade_id="open-btc",
            symbol="BTCUSDT",
            side="BUY",
            entry_price=100.0,
            executed_quantity=10.0,
            notional=1000.0,
            fee_paid=0.0,
        )
        request = TradeRequest(
            user_id="u1",
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            confidence=0.8,
            reason="same coin block",
            requested_notional=100.0,
        )

        with self.assertRaisesRegex(ValueError, "active trade already exists"):
            asyncio.run(orchestrator.execute_signal(request))

    def test_max_active_trades_blocks_new_trade(self):
        orchestrator, _ = self._build_orchestrator()
        for index, symbol in enumerate(["BTCUSDT", "ETHUSDT", "SOLUSDT"], start=1):
            trade_id = f"open-{index}"
            orchestrator.redis_state_manager.save_active_trade(
                trade_id,
                {
                    "trade_id": trade_id,
                    "user_id": "u1",
                    "symbol": symbol,
                    "side": "BUY",
                    "entry": 100.0,
                    "executed_quantity": 5.0,
                    "notional": 500.0,
                    "fees": 0.0,
                },
            )
            orchestrator.portfolio_ledger.record_trade_open(
                user_id="u1",
                trade_id=trade_id,
                symbol=symbol,
                side="BUY",
                entry_price=100.0,
                executed_quantity=5.0,
                notional=500.0,
                fee_paid=0.0,
            )
        request = TradeRequest(
            user_id="u1",
            symbol="XRPUSDT",
            side="BUY",
            order_type="MARKET",
            confidence=0.8,
            reason="max active trades test",
            requested_notional=100.0,
        )

        with self.assertRaisesRegex(ValueError, "Maximum active trades reached"):
            asyncio.run(orchestrator.execute_signal(request))

    def test_portfolio_controls_block_trade_when_total_exposure_is_full(self):
        orchestrator, _ = self._build_orchestrator()
        orchestrator.settings.max_portfolio_exposure_pct = 0.20
        existing_trade = {
            "trade_id": "open-1",
            "user_id": "u1",
            "symbol": "ETHUSDT",
            "side": "BUY",
            "entry": 100.0,
            "executed_quantity": 20.0,
            "notional": 2000.0,
            "fees": 0.0,
        }
        orchestrator.redis_state_manager.save_active_trade("open-1", existing_trade)
        if orchestrator.portfolio_ledger is not None:
            orchestrator.portfolio_ledger.record_trade_open(
                user_id="u1",
                trade_id="open-1",
                symbol="ETHUSDT",
                side="BUY",
                entry_price=100.0,
                executed_quantity=20.0,
                notional=2000.0,
                fee_paid=0.0,
            )
        request = TradeRequest(
            user_id="u1",
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            confidence=0.8,
            reason="portfolio block test",
            requested_notional=1000.0,
            expected_return=0.01,
            feature_snapshot={"15m_volume": 500000.0, "volatility": 0.01},
        )

        with self.assertRaisesRegex(ValueError, "Portfolio exposure limit reached"):
            asyncio.run(orchestrator.execute_signal(request))

    def test_portfolio_controls_block_trade_when_side_exposure_is_full(self):
        orchestrator, _ = self._build_orchestrator()
        orchestrator.settings.max_portfolio_side_exposure_pct = 0.20
        existing_trade = {
            "trade_id": "open-1",
            "user_id": "u1",
            "symbol": "ETHUSDT",
            "side": "BUY",
            "entry": 100.0,
            "executed_quantity": 20.0,
            "notional": 2000.0,
            "fees": 0.0,
        }
        orchestrator.redis_state_manager.save_active_trade("open-1", existing_trade)
        if orchestrator.portfolio_ledger is not None:
            orchestrator.portfolio_ledger.record_trade_open(
                user_id="u1",
                trade_id="open-1",
                symbol="ETHUSDT",
                side="BUY",
                entry_price=100.0,
                executed_quantity=20.0,
                notional=2000.0,
                fee_paid=0.0,
            )
        request = TradeRequest(
            user_id="u1",
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            confidence=0.8,
            reason="portfolio side block test",
            requested_notional=1000.0,
            expected_return=0.01,
            feature_snapshot={"15m_volume": 500000.0, "volatility": 0.01},
        )

        with self.assertRaisesRegex(ValueError, "Portfolio side exposure limit reached"):
            asyncio.run(orchestrator.execute_signal(request))

    def test_portfolio_correlation_uses_historical_returns(self):
        market_data = StubMarketData()
        orchestrator, _ = self._build_orchestrator(market_data=market_data)
        orchestrator.redis_state_manager.save_active_trade(
            "open-1",
            {
                "trade_id": "open-1",
                "user_id": "u1",
                "symbol": "ETHUSDT",
                "side": "BUY",
                "entry": 50.0,
                "executed_quantity": 20.0,
                "notional": 1000.0,
                "fees": 0.0,
            },
        )
        orchestrator.portfolio_ledger.record_trade_open(
            user_id="u1",
            trade_id="open-1",
            symbol="ETHUSDT",
            side="BUY",
            entry_price=50.0,
            executed_quantity=20.0,
            notional=1000.0,
            fee_paid=0.0,
        )

        correlation = asyncio.run(
            orchestrator._portfolio_correlation(
                user_id="u1",
                symbol="BTCUSDT",
                features={"15m_return": 0.01},
            )
        )

        self.assertGreater(correlation, 0.95)

    def test_portfolio_controls_block_trade_when_theme_exposure_is_full(self):
        orchestrator, _ = self._build_orchestrator()
        orchestrator.settings.max_portfolio_theme_exposure_pct = 0.20
        orchestrator.redis_state_manager.save_active_trade(
            "theme-1",
            {
                "trade_id": "theme-1",
                "user_id": "u1",
                "symbol": "ETHUSDT",
                "side": "BUY",
                "entry": 100.0,
                "executed_quantity": 20.0,
                "notional": 2000.0,
                "fees": 0.0,
            },
        )
        orchestrator.portfolio_ledger.record_trade_open(
            user_id="u1",
            trade_id="theme-1",
            symbol="ETHUSDT",
            side="BUY",
            entry_price=100.0,
            executed_quantity=20.0,
            notional=2000.0,
            fee_paid=0.0,
        )
        request = TradeRequest(
            user_id="u1",
            symbol="SOLUSDT",
            side="BUY",
            order_type="MARKET",
            confidence=0.8,
            reason="theme test",
            requested_notional=300.0,
            expected_return=0.02,
            feature_snapshot={"15m_volume": 500000.0},
        )

        with self.assertRaisesRegex(ValueError, "Portfolio theme exposure limit reached"):
            asyncio.run(orchestrator.execute_signal(request))

    def test_portfolio_controls_block_trade_when_cluster_exposure_is_full(self):
        orchestrator, _ = self._build_orchestrator()
        orchestrator.settings.max_portfolio_cluster_exposure_pct = 0.20
        orchestrator.settings.portfolio_correlation_min_overlap = 10
        orchestrator.redis_state_manager.save_active_trade(
            "cluster-1",
            {
                "trade_id": "cluster-1",
                "user_id": "u1",
                "symbol": "ETHUSDT",
                "side": "BUY",
                "entry": 100.0,
                "executed_quantity": 20.0,
                "notional": 2000.0,
                "fees": 0.0,
            },
        )
        orchestrator.portfolio_ledger.record_trade_open(
            user_id="u1",
            trade_id="cluster-1",
            symbol="ETHUSDT",
            side="BUY",
            entry_price=100.0,
            executed_quantity=20.0,
            notional=2000.0,
            fee_paid=0.0,
        )
        request = TradeRequest(
            user_id="u1",
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            confidence=0.8,
            reason="cluster test",
            requested_notional=300.0,
            expected_return=0.02,
            feature_snapshot={"15m_volume": 500000.0},
        )

        with self.assertRaisesRegex(ValueError, "Portfolio cluster exposure limit reached"):
            asyncio.run(orchestrator.execute_signal(request))

    def test_recovery_reconciles_submitted_trade_after_crash(self):
        orchestrator, _ = self._build_orchestrator()
        orchestrator.redis_state_manager.save_active_trade(
            "trade-1",
            {
                "trade_id": "trade-1",
                "symbol": "BTCUSDT",
                "status": "SUBMITTED",
                "order_id": "101",
            },
        )

        reconciled = orchestrator.reconcile_startup_state()
        restored = orchestrator.redis_state_manager.load_active_trade("trade-1")

        self.assertEqual(reconciled[0]["action"], "update_remaining")
        self.assertEqual(restored["status"], "PARTIAL")

    def test_trade_safety_blocks_excessive_slippage(self):
        orchestrator, _ = self._build_orchestrator(
            market_data=StubMarketData(
                order_book={
                    "bids": [{"price": 99.0, "qty": 20.0}],
                    "asks": [{"price": 100.0, "qty": 1.0}, {"price": 110.0, "qty": 19.0}],
                }
            )
        )
        request = TradeRequest(
            user_id="u1",
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            confidence=0.8,
            reason="safety slippage test",
            quantity=1_000.0,
            feature_snapshot={"15m_volume": 500000.0, "volatility": 0.01},
        )

        with self.assertRaisesRegex(ValueError, "estimated slippage"):
            asyncio.run(orchestrator.execute_signal(request))

    def test_trade_safety_blocks_insufficient_liquidity(self):
        orchestrator, _ = self._build_orchestrator(
            market_data=StubMarketData(
                order_book={
                    "bids": [{"price": 99.9, "qty": 0.4}],
                    "asks": [{"price": 100.1, "qty": 0.4}],
                }
            )
        )
        request = TradeRequest(
            user_id="u1",
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            confidence=0.8,
            reason="safety liquidity test",
            quantity=100.0,
            feature_snapshot={"15m_volume": 500000.0, "volatility": 0.01},
        )

        with self.assertRaisesRegex(ValueError, "liquidity coverage"):
            asyncio.run(orchestrator.execute_signal(request))

    def test_trade_safety_blocks_abnormal_volatility(self):
        orchestrator, _ = self._build_orchestrator()
        request = TradeRequest(
            user_id="u1",
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            confidence=0.8,
            reason="safety volatility test",
            requested_notional=100.0,
            feature_snapshot={"15m_volume": 500000.0, "volatility": 0.08},
        )

        with self.assertRaisesRegex(ValueError, "volatility"):
            asyncio.run(orchestrator.execute_signal(request))

    def test_low_ai_confidence_falls_back_to_rule_based_strategy(self):
        orchestrator, _ = self._build_orchestrator()

        class StubLowConfidenceAI:
            def infer(self, snapshot):
                return type("Inference", (), {
                    "price_forecast_return": 0.01,
                    "expected_return": 0.005,
                    "expected_risk": 0.02,
                    "trade_probability": 0.41,
                    "confidence_score": 0.41,
                    "decision": "BUY",
                    "model_version": "v1",
                    "model_breakdown": {},
                    "reason": "weak_ai",
                })()

        class StubStrategyDecision:
            signal = "SELL"
            confidence = 0.78
            strategy = "breakout"
            metadata = {"adjusted_confidence": 0.78}

        snapshot = type("Snapshot", (), {
            "volatility": 0.02,
            "atr": 2.0,
            "price": 100.0,
        })()
        orchestrator.ai_engine = StubLowConfidenceAI()

        inference, ai_layer = orchestrator._resolve_ai_inference(snapshot, StubStrategyDecision())

        self.assertEqual(inference.decision, "SELL")
        self.assertEqual(ai_layer["mode"], "rule_based")
        self.assertEqual(ai_layer["reason"], "ai_low_confidence")
        self.assertFalse(ai_layer["disabled"])

    def test_ai_failure_disables_ai_layer_and_uses_rule_based_fallback(self):
        orchestrator, _ = self._build_orchestrator()

        class FailingAI:
            def infer(self, snapshot):
                raise RuntimeError("model crashed")

        class StubStrategyDecision:
            signal = "BUY"
            confidence = 0.82
            strategy = "ema_crossover"
            metadata = {"adjusted_confidence": 0.82}

        snapshot = type("Snapshot", (), {
            "volatility": 0.02,
            "atr": 2.0,
            "price": 100.0,
        })()
        orchestrator.ai_engine = FailingAI()

        inference, ai_layer = orchestrator._resolve_ai_inference(snapshot, StubStrategyDecision())

        self.assertEqual(inference.decision, "BUY")
        self.assertEqual(ai_layer["mode"], "rule_based")
        self.assertEqual(ai_layer["reason"], "ai_model_failure")
        self.assertTrue(ai_layer["disabled"])
        self.assertEqual(orchestrator.cache.get("ai:layer_disabled"), "1")

    def test_disabled_ai_layer_skips_ai_and_uses_rule_based_fallback(self):
        orchestrator, _ = self._build_orchestrator()

        class ExplodingAI:
            def infer(self, snapshot):
                raise AssertionError("AI should not be called while disabled")

        class StubStrategyDecision:
            signal = "BUY"
            confidence = 0.74
            strategy = "hybrid_crypto"
            metadata = {"adjusted_confidence": 0.74}

        snapshot = type("Snapshot", (), {
            "volatility": 0.02,
            "atr": 2.0,
            "price": 100.0,
        })()
        orchestrator.cache.set("ai:layer_disabled", "1", ttl=300)
        orchestrator.ai_engine = ExplodingAI()

        inference, ai_layer = orchestrator._resolve_ai_inference(snapshot, StubStrategyDecision())

        self.assertEqual(inference.decision, "BUY")
        self.assertEqual(ai_layer["reason"], "ai_layer_disabled")
        self.assertTrue(ai_layer["disabled"])

    def test_manual_emergency_stop_blocks_execution(self):
        orchestrator, _ = self._build_orchestrator()
        orchestrator.drawdown_protection.activate_emergency_stop(
            "u1",
            reason="manual_stop",
            manual=True,
        )
        request = TradeRequest(
            user_id="u1",
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            confidence=0.8,
            reason="manual stop test",
            requested_notional=100.0,
            feature_snapshot={"15m_volume": 500000.0, "volatility": 0.01},
        )

        with self.assertRaisesRegex(ValueError, "emergency stop"):
            asyncio.run(orchestrator.execute_signal(request))

    def test_user_capital_allocation_limit_caps_trade_size(self):
        orchestrator, firestore = self._build_orchestrator()
        orchestrator.drawdown_protection.update_controls(
            "u1",
            max_capital_allocation_pct=0.01,
        )
        request = TradeRequest(
            user_id="u1",
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            confidence=0.8,
            reason="capital cap test",
            requested_notional=1_000.0,
            expected_return=0.01,
            feature_snapshot={"15m_volume": 500000.0, "volatility": 0.01},
        )

        response = asyncio.run(orchestrator.execute_signal(request))
        saved_trade = firestore.trades[-1]

        self.assertEqual(response.status, "FILLED")
        self.assertLessEqual(saved_trade["requested_notional"], 100.0)

    def test_auto_emergency_stop_blocks_after_daily_loss_breach(self):
        orchestrator, _ = self._build_orchestrator()
        orchestrator.drawdown_protection.update_controls(
            "u1",
            daily_loss_limit=0.02,
        )
        orchestrator.drawdown_protection.update("u1", 10_000)
        orchestrator.drawdown_protection.update("u1", 9_700)
        request = TradeRequest(
            user_id="u1",
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            confidence=0.8,
            reason="auto emergency stop test",
            requested_notional=100.0,
            feature_snapshot={"15m_volume": 500000.0, "volatility": 0.01},
        )

        with self.assertRaisesRegex(ValueError, "emergency stop"):
            asyncio.run(orchestrator.execute_signal(request))


if __name__ == "__main__":
    unittest.main()
