from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI

from backend.api.routes.monitor import create_monitor_router
from backend.api.routes.state import create_state_router
from backend.api.signal import SignalRouterContext, create_signal_router
from backend.db.database import SQLiteTradeDatabase
from backend.engine.execution_engine import ExecutionEngine
from backend.engine.meta_engine import MetaEngine
from backend.engine.monitor_engine import MarketPriceStore, MonitorEngine, TradeLifecycleLoop
from backend.engine.risk_engine import RiskEngine
from backend.engine.sync_engine import BrokerSyncLoop, SyncEngine
from backend.services import BrokerAdapter, PriceService, create_broker_adapter
from backend.utils.logger import get_logger


logger = get_logger("trading-system")
BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = BASE_DIR / "config" / "settings.yaml"
DEFAULT_DB_PATH = BASE_DIR / "backend" / "artifacts" / "trades.db"


@dataclass
class TradingSystemContext:
    db: SQLiteTradeDatabase
    broker: BrokerAdapter
    meta_engine: MetaEngine
    risk_engine: RiskEngine
    execution_engine: ExecutionEngine
    monitor_engine: MonitorEngine
    sync_engine: SyncEngine
    price_store: MarketPriceStore
    price_service: PriceService
    lifecycle_loop: TradeLifecycleLoop
    sync_loop: BrokerSyncLoop
    strategies: list[str]
    config: dict[str, Any]


def load_config(config_path: str | Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    with Path(config_path).open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    return raw if isinstance(raw, dict) else {}


def build_context(
    *,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> TradingSystemContext:
    config = load_config(config_path)
    strategies = [str(item).strip().lower() for item in config.get("strategies", []) if str(item).strip()]
    execution_config = {
        **config.get("execution_engine", {}),
        **config.get("execution", {}),
    }
    broker_config = config.get("broker", {})
    sync_config = config.get("sync_engine", {})
    db = SQLiteTradeDatabase(db_path)
    broker = create_broker_adapter(broker_config if isinstance(broker_config, dict) else {})

    meta_engine = MetaEngine(
        db,
        last_n_trades=int(config.get("meta_engine", {}).get("last_n_trades", 20)),
        min_history=int(config.get("meta_engine", {}).get("min_history", 3)),
        recent_trade_window=int(config.get("meta_engine", {}).get("recent_trade_window", 10)),
        weak_strategy_threshold=float(config.get("meta_engine", {}).get("weak_strategy_threshold", 0.2)),
        kill_switch_score=float(config.get("meta_engine", {}).get("kill_switch_score", 0.0)),
    )
    risk_engine = RiskEngine(
        db,
        account_equity=float(config.get("app", {}).get("account_equity", 10_000)),
        max_risk_per_trade_pct=float(config.get("risk_engine", {}).get("max_risk_per_trade_pct", 0.02)),
        max_daily_loss_pct=float(config.get("risk_engine", {}).get("max_daily_loss_pct", 0.03)),
        max_consecutive_losses=int(config.get("risk_engine", {}).get("max_consecutive_losses", 3)),
        stop_loss_pct=float(config.get("risk_engine", {}).get("stop_loss_pct", 0.01)),
        take_profit_pct=float(config.get("risk_engine", {}).get("take_profit_pct", 0.02)),
        stop_loss_atr_multiplier=float(config.get("risk_engine", {}).get("stop_loss_atr_multiplier", 1.5)),
        take_profit_atr_multiplier=float(config.get("risk_engine", {}).get("take_profit_atr_multiplier", 3.0)),
    )
    execution_engine = ExecutionEngine(
        db,
        broker,
        account_equity=float(config.get("app", {}).get("account_equity", 10_000)),
        risk_per_trade_pct=float(execution_config.get("risk_per_trade_pct", 0.02)),
        min_confidence=float(execution_config.get("min_confidence", 0.3)),
        cooldown_minutes=int(execution_config.get("cooldown_minutes", 15)),
        max_open_trades=int(execution_config.get("max_open_trades", 2)),
        dry_run=bool(broker_config.get("dry_run", False)) if isinstance(broker_config, dict) else False,
        kill_switch=bool(broker_config.get("kill_switch", False)) if isinstance(broker_config, dict) else False,
        max_total_exposure_pct=float(broker_config.get("max_total_exposure_pct", 3.0)) if isinstance(broker_config, dict) else 3.0,
    )
    price_store = MarketPriceStore()
    price_service = PriceService(
        base_url=str(config.get("monitor_engine", {}).get("price_api_base_url", "https://api.binance.com")),
        secondary_base_url=str(config.get("monitor_engine", {}).get("secondary_price_api_base_url", "https://api.bybit.com")),
        timeout_seconds=float(config.get("monitor_engine", {}).get("price_timeout_seconds", 5.0)),
        cache_max_age_seconds=float(config.get("monitor_engine", {}).get("cache_max_age_seconds", 10.0)),
        mismatch_threshold_pct=float(config.get("monitor_engine", {}).get("mismatch_threshold_pct", 0.002)),
    )
    monitor_engine = MonitorEngine(
        db,
        cache_exit_threshold_pct=float(config.get("monitor_engine", {}).get("cache_exit_threshold_pct", 0.0015)),
        slippage_bps=float(execution_config.get("slippage_bps", 10.0)),
        min_tick=float(execution_config.get("min_tick", 0.01)),
    )
    lifecycle_loop = TradeLifecycleLoop(
        db,
        monitor_engine,
        price_store,
        price_service,
        poll_interval_seconds=float(config.get("monitor_engine", {}).get("poll_interval_seconds", 3.0)),
    )
    sync_engine = SyncEngine(
        db,
        broker,
        attach_orphan_positions=bool(sync_config.get("attach_orphan_positions", False)) if isinstance(sync_config, dict) else False,
    )
    sync_loop = BrokerSyncLoop(
        sync_engine,
        poll_interval_seconds=float(sync_config.get("poll_interval_seconds", 5.0)) if isinstance(sync_config, dict) else 5.0,
    )
    return TradingSystemContext(
        db=db,
        broker=broker,
        meta_engine=meta_engine,
        risk_engine=risk_engine,
        execution_engine=execution_engine,
        monitor_engine=monitor_engine,
        sync_engine=sync_engine,
        price_store=price_store,
        price_service=price_service,
        lifecycle_loop=lifecycle_loop,
        sync_loop=sync_loop,
        strategies=strategies,
        config=config,
    )


def create_app(
    *,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> FastAPI:
    context = build_context(config_path=config_path, db_path=db_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        del app
        if bool(context.config.get("sync_engine", {}).get("auto_start", True)):
            await context.sync_loop.start()
        if bool(context.config.get("monitor_engine", {}).get("auto_start", True)):
            await context.lifecycle_loop.start()
        try:
            yield
        finally:
            await context.lifecycle_loop.stop()
            await context.sync_loop.stop()

    app = FastAPI(title="AI Trading System", version="0.1.0", lifespan=lifespan)
    app.state.trading = context

    app.include_router(
        create_signal_router(
            SignalRouterContext(
                meta_engine=context.meta_engine,
                risk_engine=context.risk_engine,
                execution_engine=context.execution_engine,
                strategies=context.strategies,
            )
        )
    )
    app.include_router(create_state_router(context.db, context.meta_engine, context.strategies))
    app.include_router(create_monitor_router(context.price_store, context.lifecycle_loop, context.sync_engine))

    @app.get("/")
    def root() -> dict[str, str]:
        return {
            "service": str(context.config.get("app", {}).get("name", "ai-trading-system")),
            "status": "running",
        }

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    logger.info("trading system booted strategies=%s db=%s", context.strategies, Path(db_path))
    return app


app = create_app()
