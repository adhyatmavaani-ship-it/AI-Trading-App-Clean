from __future__ import annotations

from functools import lru_cache

from db.database import SQLiteTradeDatabase

from app.core.config import get_settings
from app.services.adaptive_learning import AdaptiveLearningService
from app.services.ai_copilot import AICopilotService
from app.services.ai_engine import AIEngine
from app.services.alpha_engine import AlphaEngine
from app.services.analytics_service import AnalyticsService
from app.services.alerting import AlertingService
from app.services.allocation_engine import AllocationEngine
from app.services.automated_journal import AutomatedJournalService
from app.services.backtest_jobs import BacktestJobService
from app.services.backtesting import BacktestingEngine
from app.services.broker_reconciliation import BrokerReconciliationEngine
from app.services.broker_state_sync import BrokerStateSyncService
from app.services.drawdown_protection import DrawdownProtectionService
from app.services.dual_track_engine import DualTrackCoordinator
from app.services.evolution_lab import EvolutionLab
from app.services.execution_engine import ExecutionEngine
from app.services.execution_circuit_breaker import ExecutionCircuitBreaker
from app.services.event_dispatcher import EventDispatcher
from app.services.execution_idempotency import ExecutionIdempotencyService
from app.services.execution_queue_manager import ExecutionQueueManager
from app.services.feature_pipeline import FeaturePipeline
from app.services.firestore_repo import FirestoreRepository
from app.services.latency_monitor import LatencyMonitor
from app.services.liquidity_monitor import LiquidityMonitor
from app.services.market_data import MarketDataService
from app.services.market_feed_watchdog import MarketFeedWatchdog
from app.services.market_universe_scanner import MarketUniverseScanner
from app.services.meta_controller import MetaController
from app.services.model_stability import ModelStabilityService
from app.services.micro_mode_controller import MicroModeController
from app.services.multi_agent_consensus import MultiAgentConsensusEngine
from app.services.multi_chain_router import MultiChainRouter
from app.services.narrative_macro_intelligence import NarrativeMacroIntelligenceEngine
from app.services.generative_simulation_engine import GenerativeSimulationEngine
from app.services.historical_data import HistoricalDataService
from app.services.paper_execution import PaperExecutionEngine
from app.services.performance_tracker import PerformanceTracker
from app.services.portfolio_manager import PortfolioManager
from app.services.portfolio_ledger import PortfolioLedgerService
from app.services.model_registry import ModelRegistry
from app.services.pro_scanner import ProScannerService
from app.services.regime_detector import RegimeDetector
from app.services.redis_cache import RedisCache
from app.services.redis_state_manager import RedisStateManager
from app.services.retrain_trigger_service import RetrainTriggerService
from app.services.risk_controller import RiskController
from app.services.risk_engine import RiskEngine
from app.services.rollout_manager import RolloutManager
from app.services.scanner_service import ScannerService
from app.services.shard_manager import ShardManager
from app.services.signal_broadcaster import SignalBroadcaster
from app.services.signal_websocket_manager import get_signal_websocket_manager
from app.services.security_scanner import SecurityScanner
from app.services.sentiment_engine import SentimentEngine
from app.services.shadow_liquidity_engine import ShadowLiquiditySentinel
from app.services.self_healing_ppo import SelfHealingPPOService
from app.services.simulation_tester import SimulationTester
from app.services.safety_state import SafetyStateService
from app.services.strategy_controller import StrategyController
from app.services.strategy_marketplace import StrategyMarketplaceService
from app.services.strategy_engine import StrategyEngine
from app.services.system_monitor import SystemMonitorService
from app.services.tax_engine import TaxEngine
from app.services.trade_probability import TradeProbabilityEngine
from app.services.trading_orchestrator import TradingOrchestrator
from app.services.user_experience_engine import UserExperienceEngine
from app.services.virtual_order_manager import VirtualOrderManager
from app.services.whale_tracker import WhaleTracker
from app.workers.strategy_optimizer_worker import StrategyOptimizerWorker
from app.workers.trade_monitor_worker import ActiveTradeMonitorWorker
from app.workers.broker_reconciliation_worker import BrokerReconciliationWorker
from app.workers.broker_state_sync_worker import BrokerStateSyncWorker
from app.workers.event_dispatcher_worker import EventDispatcherWorker


class ServiceContainer:
    def __init__(self):
        settings = get_settings()
        cache = RedisCache(settings.redis_url)
        firestore = FirestoreRepository(
            settings.firestore_project_id,
            raw_credentials_json=settings.google_credentials_json,
            local_training_buffer_path=settings.training_buffer_path,
        )
        pro_store = SQLiteTradeDatabase(settings.pro_storage_path)
        registry = ModelRegistry(settings)
        market_data = MarketDataService(settings, cache)
        feature_pipeline = FeaturePipeline(RegimeDetector(settings))
        ai_engine = AIEngine(registry)
        trade_probability_engine = TradeProbabilityEngine(
            settings=settings,
            registry=registry,
            firestore=firestore,
        )
        strategy_engine = StrategyEngine(probability_engine=trade_probability_engine)
        risk_engine = RiskEngine(settings)
        execution_engine = ExecutionEngine(settings)
        execution_circuit_breaker = ExecutionCircuitBreaker(settings=settings, cache=cache)
        execution_idempotency_service = ExecutionIdempotencyService(settings=settings, cache=cache, store=pro_store)
        execution_engine.execution_store = pro_store
        paper_execution_engine = PaperExecutionEngine(settings, market_data)
        self.alerting_service = AlertingService(settings.alert_webhook_url)
        drawdown_protection = DrawdownProtectionService(settings, cache)
        system_monitor = SystemMonitorService(settings, cache)
        model_stability = ModelStabilityService(settings, registry, cache)
        rollout_manager = RolloutManager(settings, cache)
        alpha_engine = AlphaEngine()
        latency_monitor = LatencyMonitor(settings, cache)
        micro_mode_controller = MicroModeController(settings, cache)
        whale_tracker = WhaleTracker.create_default()
        liquidity_monitor = LiquidityMonitor()
        sentiment_engine = SentimentEngine()
        self_healing_service = SelfHealingPPOService(settings=settings, cache=cache, firestore=firestore)
        adaptive_learning_service = AdaptiveLearningService(settings=settings, cache=cache, firestore=firestore)
        security_scanner = SecurityScanner()
        multi_chain_router = MultiChainRouter(settings)
        multi_agent_consensus = MultiAgentConsensusEngine.create_default()
        redis_state_manager = RedisStateManager(settings, cache)
        shadow_liquidity_sentinel = ShadowLiquiditySentinel(settings=settings, cache=cache, firestore=firestore)
        narrative_macro_intelligence = NarrativeMacroIntelligenceEngine(
            settings=settings,
            redis_state_manager=redis_state_manager,
            firestore=firestore,
        )
        generative_simulation_engine = GenerativeSimulationEngine(settings=settings, cache=cache, firestore=firestore)
        evolution_lab = EvolutionLab(settings=settings, cache=cache, firestore=firestore)
        tax_engine = TaxEngine()
        performance_tracker = PerformanceTracker(cache, firestore)
        portfolio_ledger = PortfolioLedgerService(
            settings=settings,
            cache=cache,
            market_data=market_data,
            redis_state_manager=redis_state_manager,
            firestore=firestore,
        )
        portfolio_manager = PortfolioManager(settings)
        user_experience_engine = UserExperienceEngine(settings=settings, cache=cache)
        market_feed_watchdog = MarketFeedWatchdog(settings=settings, cache=cache)
        safety_state_service = SafetyStateService(settings=settings, cache=cache, store=pro_store)
        scanner_service = ScannerService(
            settings=settings,
            cache=cache,
            market_data=market_data,
        )
        market_universe_scanner = MarketUniverseScanner(
            settings=settings,
            market_data=market_data,
            user_experience_engine=user_experience_engine,
            scanner_service=scanner_service,
            market_feed_watchdog=market_feed_watchdog,
        )
        ai_copilot_service = AICopilotService(market_data=market_data, store=pro_store)
        pro_scanner_service = ProScannerService(
            market_data=market_data,
            scanner_service=scanner_service,
            alerting_service=self.alerting_service,
            store=pro_store,
        )
        strategy_marketplace_service = StrategyMarketplaceService(cache=cache, store=pro_store)
        automated_journal_service = AutomatedJournalService(cache=cache, store=pro_store)
        analytics_service = AnalyticsService(
            settings=settings,
            cache=cache,
            redis_state_manager=redis_state_manager,
            firestore=firestore,
        )
        strategy_controller = StrategyController(
            settings=settings,
            analytics=analytics_service,
            cache=cache,
        )
        retrain_trigger_service = RetrainTriggerService(
            settings=settings,
            cache=cache,
            trade_probability_engine=trade_probability_engine,
        )
        allocation_engine = AllocationEngine(precision=settings.virtual_order_precision)
        virtual_order_manager = VirtualOrderManager(settings, cache, allocation_engine)
        shard_manager = ShardManager(settings)
        execution_queue_manager = ExecutionQueueManager(settings, cache, shard_manager)
        signal_websocket_manager = get_signal_websocket_manager()
        signal_broadcaster = SignalBroadcaster(
            settings=settings,
            cache=cache,
            queue_manager=execution_queue_manager,
        )
        risk_controller = RiskController(
            settings=settings,
            cache=cache,
            drawdown_protection=drawdown_protection,
            signal_broadcaster=signal_broadcaster,
        )
        meta_controller = MetaController(
            settings=settings,
            cache=cache,
            system_monitor=system_monitor,
            drawdown_protection=drawdown_protection,
            risk_engine=risk_engine,
            rollout_manager=rollout_manager,
            model_stability=model_stability,
            redis_state_manager=redis_state_manager,
            firestore=firestore,
            portfolio_ledger=portfolio_ledger,
        )
        dual_track_coordinator = DualTrackCoordinator(
            settings=settings,
            cache=cache,
            market_data=market_data,
            feature_pipeline=feature_pipeline,
            sentiment_engine=sentiment_engine,
            whale_tracker=whale_tracker,
            liquidity_monitor=liquidity_monitor,
            multi_chain_router=multi_chain_router,
            drawdown_protection=drawdown_protection,
            narrative_macro_intelligence=narrative_macro_intelligence,
        )

        self.trading_orchestrator = TradingOrchestrator(
            settings=settings,
            market_data=market_data,
            feature_pipeline=feature_pipeline,
            ai_engine=ai_engine,
            strategy_engine=strategy_engine,
            risk_engine=risk_engine,
            execution_engine=execution_engine,
            paper_execution_engine=paper_execution_engine,
            cache=cache,
            drawdown_protection=drawdown_protection,
            system_monitor=system_monitor,
            rollout_manager=rollout_manager,
            model_stability=model_stability,
            alpha_engine=alpha_engine,
            micro_mode_controller=micro_mode_controller,
            whale_tracker=whale_tracker,
            liquidity_monitor=liquidity_monitor,
            sentiment_engine=sentiment_engine,
            security_scanner=security_scanner,
            multi_chain_router=multi_chain_router,
            tax_engine=tax_engine,
            redis_state_manager=redis_state_manager,
            performance_tracker=performance_tracker,
            portfolio_ledger=portfolio_ledger,
            portfolio_manager=portfolio_manager,
            firestore=firestore,
            virtual_order_manager=virtual_order_manager,
            shard_manager=shard_manager,
            execution_queue_manager=execution_queue_manager,
            signal_broadcaster=signal_broadcaster,
            self_healing_service=self_healing_service,
            latency_monitor=latency_monitor,
            meta_controller=meta_controller,
            analytics_service=analytics_service,
            strategy_controller=strategy_controller,
            user_experience_engine=user_experience_engine,
            risk_controller=risk_controller,
            adaptive_learning_service=adaptive_learning_service,
        )
        active_trade_monitor = ActiveTradeMonitorWorker(
            settings=settings,
            redis_state_manager=redis_state_manager,
            market_data=market_data,
            feature_pipeline=feature_pipeline,
            trading_orchestrator=self.trading_orchestrator,
        )
        strategy_optimizer = StrategyOptimizerWorker(
            settings=settings,
            strategy_controller=strategy_controller,
        )
        broker_reconciliation_engine = BrokerReconciliationEngine(
            settings=settings,
            execution_engine=execution_engine,
            redis_state_manager=redis_state_manager,
            cache=cache,
            store=pro_store,
        )
        broker_reconciliation_worker = BrokerReconciliationWorker(
            settings=settings,
            reconciliation_engine=broker_reconciliation_engine,
        )
        broker_state_sync_service = BrokerStateSyncService(
            settings=settings,
            execution_engine=execution_engine,
            cache=cache,
            store=pro_store,
        )
        broker_state_sync_worker = BrokerStateSyncWorker(
            settings=settings,
            sync_service=broker_state_sync_service,
        )
        event_dispatcher = EventDispatcher(
            store=pro_store,
            cache=cache,
            batch_size=int(settings.execution_event_dispatcher_batch_size),
            max_attempts=int(settings.execution_event_dispatcher_max_attempts),
            stall_seconds=float(settings.execution_event_dispatcher_stall_seconds),
            backlog_warning_threshold=int(settings.execution_event_outbox_warning_threshold),
            backlog_critical_threshold=int(settings.execution_event_outbox_critical_threshold),
        )
        event_dispatcher_worker = EventDispatcherWorker(
            dispatcher=event_dispatcher,
            interval_seconds=float(settings.execution_event_dispatcher_interval_seconds),
            enabled=bool(settings.execution_event_dispatcher_enabled),
        )
        self.trading_orchestrator.active_trade_monitor = active_trade_monitor
        self.trading_orchestrator.reconcile_startup_state()
        broker_reconciliation_engine.startup_recovery_report()
        self.backtesting_engine = BacktestingEngine(
            settings=settings,
            market_data=market_data,
            feature_pipeline=feature_pipeline,
            ai_engine=ai_engine,
            strategy_engine=strategy_engine,
            risk_engine=risk_engine,
        )
        self.historical_data = HistoricalDataService(settings=settings)
        self.backtest_job_service = BacktestJobService(
            settings=settings,
            backtesting_engine=self.backtesting_engine,
            historical_data=self.historical_data,
        )
        self.drawdown_protection = drawdown_protection
        self.cache = cache
        self.firestore = firestore
        self.pro_store = pro_store
        self.settings = settings
        self.market_data = market_data
        self.market_feed_watchdog = market_feed_watchdog
        self.execution_circuit_breaker = execution_circuit_breaker
        self.execution_idempotency_service = execution_idempotency_service
        self.safety_state_service = safety_state_service
        self.system_monitor = system_monitor
        self.model_stability = model_stability
        self.rollout_manager = rollout_manager
        self.alpha_engine = alpha_engine
        self.latency_monitor = latency_monitor
        self.micro_mode_controller = micro_mode_controller
        self.whale_tracker = whale_tracker
        self.liquidity_monitor = liquidity_monitor
        self.sentiment_engine = sentiment_engine
        self.self_healing_service = self_healing_service
        self.adaptive_learning_service = adaptive_learning_service
        self.security_scanner = security_scanner
        self.multi_chain_router = multi_chain_router
        self.multi_agent_consensus = multi_agent_consensus
        self.shadow_liquidity_sentinel = shadow_liquidity_sentinel
        self.narrative_macro_intelligence = narrative_macro_intelligence
        self.generative_simulation_engine = generative_simulation_engine
        self.evolution_lab = evolution_lab
        self.dual_track_coordinator = dual_track_coordinator
        self.tax_engine = tax_engine
        self.redis_state_manager = redis_state_manager
        self.performance_tracker = performance_tracker
        self.portfolio_ledger = portfolio_ledger
        self.portfolio_manager = portfolio_manager
        self.allocation_engine = allocation_engine
        self.virtual_order_manager = virtual_order_manager
        self.shard_manager = shard_manager
        self.execution_queue_manager = execution_queue_manager
        self.signal_broadcaster = signal_broadcaster
        self.signal_websocket_manager = signal_websocket_manager
        self.meta_controller = meta_controller
        self.trade_probability_engine = trade_probability_engine
        self.analytics_service = analytics_service
        self.retrain_trigger_service = retrain_trigger_service
        self.strategy_controller = strategy_controller
        self.user_experience_engine = user_experience_engine
        self.scanner_service = scanner_service
        self.market_universe_scanner = market_universe_scanner
        self.ai_copilot_service = ai_copilot_service
        self.pro_scanner_service = pro_scanner_service
        self.strategy_marketplace_service = strategy_marketplace_service
        self.automated_journal_service = automated_journal_service
        self.risk_controller = risk_controller
        self.active_trade_monitor = active_trade_monitor
        self.strategy_optimizer = strategy_optimizer
        self.broker_reconciliation_engine = broker_reconciliation_engine
        self.broker_reconciliation_worker = broker_reconciliation_worker
        self.broker_state_sync_service = broker_state_sync_service
        self.broker_state_sync_worker = broker_state_sync_worker
        self.event_dispatcher = event_dispatcher
        self.event_dispatcher_worker = event_dispatcher_worker
        self.simulation_tester = SimulationTester(
            settings=settings,
            orchestrator=self.trading_orchestrator,
            risk_engine=risk_engine,
            drawdown_protection=drawdown_protection,
            monitor=system_monitor,
            paper_execution=paper_execution_engine,
        )


@lru_cache
def get_container() -> ServiceContainer:
    return ServiceContainer()
