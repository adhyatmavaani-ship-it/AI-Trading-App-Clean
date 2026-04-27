from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import json
import math
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from app.core.exceptions import RiskLimitExceededError, StateError
from app.schemas.trading import (
    AIInference,
    AlphaContext,
    AlphaDecision,
    ExplainabilityContext,
    FeatureSnapshot,
    LiquidityContext,
    SecurityContext,
    SentimentContext,
    SignalResponse,
    TaxContext,
    TradeCloseResponse,
    TradeRequest,
    TradeResponse,
    WhaleContext,
)
from app.core.config import Settings
from app.services.liquidity_slippage import LiquiditySlippageEngine
from app.services.drawdown_protection import DrawdownProtectionService
from app.services.model_stability import ModelStabilityService
from app.services.redis_cache import RedisCache
from app.services.rollout_manager import RolloutManager
from app.services.system_monitor import SystemMonitorService

if TYPE_CHECKING:
    from app.services.ai_engine import AIEngine
    from app.services.execution_engine import ExecutionEngine
    from app.services.execution_queue_manager import ExecutionQueueManager
    from app.services.feature_pipeline import FeaturePipeline
    from app.services.firestore_repo import FirestoreRepository
    from app.services.alpha_engine import AlphaEngine
    from app.services.analytics_service import AnalyticsService
    from app.services.latency_monitor import LatencyMonitor
    from app.services.liquidity_monitor import LiquidityMonitor
    from app.services.market_data import MarketDataService
    from app.services.meta_controller import MetaController
    from app.services.micro_mode_controller import MicroModeController
    from app.services.multi_chain_router import MultiChainRouter
    from app.services.performance_tracker import PerformanceTracker
    from app.services.paper_execution import PaperExecutionEngine
    from app.services.portfolio_manager import PortfolioManager
    from app.services.portfolio_ledger import PortfolioLedgerService
    from app.services.risk_controller import RiskController
    from app.services.redis_state_manager import RedisStateManager
    from app.services.risk_engine import RiskEngine
    from app.services.shard_manager import ShardManager
    from app.services.signal_broadcaster import SignalBroadcaster
    from app.services.security_scanner import SecurityScanner
    from app.services.sentiment_engine import SentimentEngine
    from app.services.self_healing_ppo import SelfHealingPPOService
    from app.services.strategy_controller import StrategyController
    from app.services.strategy_engine import StrategyEngine
    from app.services.tax_engine import TaxEngine
    from app.services.user_experience_engine import UserExperienceEngine
    from app.services.virtual_order_manager import VirtualOrderManager
    from app.services.whale_tracker import WhaleTracker

logger = logging.getLogger(__name__)


@dataclass
class TradingOrchestrator:
    settings: Settings
    market_data: MarketDataService
    feature_pipeline: FeaturePipeline
    ai_engine: AIEngine
    strategy_engine: StrategyEngine
    risk_engine: RiskEngine
    execution_engine: ExecutionEngine
    paper_execution_engine: PaperExecutionEngine
    cache: RedisCache
    drawdown_protection: DrawdownProtectionService
    system_monitor: SystemMonitorService
    rollout_manager: RolloutManager
    model_stability: ModelStabilityService
    alpha_engine: AlphaEngine
    micro_mode_controller: MicroModeController
    whale_tracker: WhaleTracker
    liquidity_monitor: LiquidityMonitor
    sentiment_engine: SentimentEngine
    security_scanner: SecurityScanner
    multi_chain_router: MultiChainRouter
    tax_engine: TaxEngine
    redis_state_manager: RedisStateManager
    performance_tracker: PerformanceTracker
    firestore: FirestoreRepository
    virtual_order_manager: VirtualOrderManager
    shard_manager: ShardManager
    execution_queue_manager: ExecutionQueueManager
    signal_broadcaster: SignalBroadcaster
    portfolio_ledger: PortfolioLedgerService | None = None
    self_healing_service: SelfHealingPPOService | None = None
    latency_monitor: LatencyMonitor | None = None
    meta_controller: MetaController | None = None
    active_trade_monitor: object | None = None
    analytics_service: AnalyticsService | None = None
    strategy_controller: StrategyController | None = None
    portfolio_manager: PortfolioManager | None = None
    user_experience_engine: UserExperienceEngine | None = None
    risk_controller: RiskController | None = None

    def __post_init__(self) -> None:
        self.trade_safety_engine = LiquiditySlippageEngine(
            slippage_threshold_bps=float(self.settings.trade_safety_max_slippage_bps),
            chunk_delay_ms=self.settings.execution_chunk_delay_ms,
        )

    def update_active_trade_state(self, trade_id: str, payload: dict) -> None:
        self.redis_state_manager.save_active_trade(trade_id, payload)
        if payload.get("signal_id"):
            self.redis_state_manager.remember_signal_trade(str(payload["signal_id"]), trade_id)
        self.redis_state_manager.register_monitored_trade(
            trade_id,
            {
                "trade_id": trade_id,
                "symbol": payload.get("symbol"),
                "user_id": payload.get("user_id"),
            },
        )

    def annotate_trade_exit(self, *, trade_id: str, exit_reason: str, exit_type: str) -> None:
        self.firestore.update_trade(
            trade_id,
            {
                "exit_reason": exit_reason,
                "exit_type": exit_type,
            },
        )

    def _log_trade_recorded(self, *, trade_id: str, symbol: str, side: str) -> None:
        extra = {
            "event": "trade_recorded",
            "context": {
                "trade_id": trade_id,
                "symbol": symbol,
                "side": side,
                "trading_mode": self.settings.trading_mode,
            },
        }
        log_method = logger.info if self.settings.trading_mode == "live" else logger.debug
        log_method("trade_recorded", extra=extra)

    def _publish_activity(
        self,
        *,
        status: str,
        message: str,
        bot_state: str,
        symbol: str | None = None,
        next_scan: str | None = None,
        confidence: float | None = None,
        action: str | None = None,
        intent: str | None = None,
        confidence_building: bool | None = None,
        readiness: float | None = None,
        reason: str | None = None,
        extra: dict | None = None,
    ) -> None:
        if self.user_experience_engine is None:
            return
        self.user_experience_engine.publish_activity(
            status=status,
            message=message,
            bot_state=bot_state,
            symbol=symbol,
            next_scan=next_scan,
            confidence=confidence,
            action=action,
            intent=intent,
            confidence_building=confidence_building,
            readiness=readiness,
            reason=reason,
            extra=extra,
        )

    async def generate_live_signals(self, limit: int = 3) -> list[SignalResponse]:
        symbols = list(self.settings.websocket_symbols or ["BTCUSDT", "ETHUSDT", "SOLUSDT"])
        target = max(1, min(limit, int(self.settings.max_active_trades)))
        ranked_symbols = sorted(
            [str(symbol).upper() for symbol in symbols[: max(target, len(symbols))]],
            key=lambda symbol: self._symbol_priority_multiplier(symbol),
            reverse=True,
        )
        generated: list[tuple[float, SignalResponse]] = []
        for index, symbol in enumerate(ranked_symbols):
            next_scan = ranked_symbols[index + 1] if index + 1 < len(ranked_symbols) else None
            self._publish_activity(
                status="scanning",
                message=f"{symbol} scan started",
                bot_state="SCANNING",
                symbol=symbol,
                next_scan=next_scan,
                intent=f"Scanning {symbol} for structure, momentum, and volume alignment",
                readiness=0.0,
            )
            try:
                signal = await self.evaluate_symbol(symbol.upper())
                score = float(signal.snapshot.features.get("strict_trade_score", 0.0) or 0.0)
                readiness = max(0.0, min(100.0, score))
                reason = str(signal.snapshot.features.get("strict_trade_reason", "setup still forming"))
                confidence_building = score >= float(self.settings.strict_trade_score_threshold) - float(self.settings.activity_near_miss_score_delta)
                intent = (
                    f"Watching {symbol} for confirmation above the execution threshold"
                    if confidence_building
                    else f"Monitoring {symbol} while confluence builds"
                )
                if signal.strategy == "LOW_CONFIDENCE_WATCHLIST":
                    if confidence_building:
                        self._publish_activity(
                            status="almost_trade",
                            message=f"{symbol} almost triggered trade ({reason})",
                            bot_state="WAITING",
                            symbol=symbol,
                            next_scan=next_scan,
                            confidence=float(signal.inference.confidence_score),
                            intent=intent,
                            confidence_building=True,
                            readiness=readiness,
                            reason=reason,
                            extra={"confidence_meter": round(float(signal.inference.confidence_score), 8), "strict_trade_score": round(score, 6), "regime": signal.snapshot.regime},
                        )
                    else:
                        self._publish_activity(
                            status="scanning",
                            message=f"{symbol} checked -> {reason}, skipped",
                            bot_state="WAITING",
                            symbol=symbol,
                            next_scan=next_scan,
                            confidence=float(signal.inference.confidence_score),
                            intent=intent,
                            confidence_building=False,
                            readiness=readiness,
                            reason=reason,
                            extra={"confidence_meter": round(float(signal.inference.confidence_score), 8), "strict_trade_score": round(score, 6), "regime": signal.snapshot.regime},
                        )
                    continue
                self._publish_activity(
                    status="opportunity_found",
                    message=f"{symbol} setup accepted -> executing candidate",
                    bot_state="ANALYZING",
                    symbol=symbol,
                    next_scan=next_scan,
                    confidence=float(signal.inference.confidence_score),
                    action="Executing trade",
                    intent=f"{symbol} is ready for execution",
                    confidence_building=True,
                    readiness=max(readiness, 70.0),
                    reason=reason,
                    extra={"confidence_meter": round(float(signal.inference.confidence_score), 8), "strict_trade_score": round(score, 6), "regime": signal.snapshot.regime},
                )
                generated.append((score * self._symbol_priority_multiplier(symbol), signal))
            except Exception as exc:
                self._publish_activity(
                    status="scanning",
                    message=f"{symbol} scan failed -> {type(exc).__name__}",
                    bot_state="WAITING",
                    symbol=symbol,
                    next_scan=next_scan,
                    intent=f"Retrying {symbol} analysis on the next cycle",
                    reason=type(exc).__name__,
                )
                logger.exception(
                    "live_signal_generation_failed",
                    extra={
                        "event": "live_signal_generation_failed",
                        "context": {"symbol": symbol.upper(), "error": str(exc)[:200]},
                    },
                )
                continue
        generated.sort(key=lambda item: item[0], reverse=True)
        if not generated:
            self._publish_activity(
                status="waiting",
                message="No safe trade found. Continuing scan.",
                bot_state="WAITING",
                intent="Waiting for high-confidence confluence before trading",
            )
        return [signal for _, signal in generated[:target]]

    async def _best_effort_live_signal(self, symbol: str, exc: Exception) -> SignalResponse:
        try:
            frames = await self.market_data.fetch_multi_timeframe_ohlcv(symbol)
            order_book = await self.market_data.fetch_order_book(symbol)
            snapshot = self.feature_pipeline.build(symbol, frames, order_book)
        except Exception as snapshot_exc:
            logger.exception(
                "best_effort_snapshot_failed",
                extra={
                    "event": "best_effort_snapshot_failed",
                    "context": {"symbol": symbol, "error": str(snapshot_exc)[:200]},
                },
            )
            latest_price = await self.market_data.fetch_latest_price(symbol)
            order_book = self.market_data._mock_order_book(latest_price)
            bid_volume = sum(level["qty"] for level in order_book.get("bids", [])[:10])
            ask_volume = sum(level["qty"] for level in order_book.get("asks", [])[:10])
            imbalance = (bid_volume - ask_volume) / max(bid_volume + ask_volume, 1e-8)
            snapshot = FeatureSnapshot(
                symbol=symbol,
                price=float(latest_price),
                timestamp=datetime.now(timezone.utc),
                regime="RANGING",
                regime_confidence=0.45,
                volatility=0.01,
                atr=float(latest_price) * 0.005,
                order_book_imbalance=float(imbalance),
                features={
                    "15m_ema_spread": float(imbalance) * 0.01,
                    "5m_rsi": 52.0 if imbalance >= 0 else 48.0,
                    "15m_return": float(imbalance) * 0.002,
                },
            )

        action = "BUY" if float(snapshot.features.get("15m_ema_spread", snapshot.order_book_imbalance)) >= 0 else "SELL"
        confidence = max(float(self.settings.signal_min_publish_confidence), 0.26)
        inference = AIInference(
            price_forecast_return=0.0,
            expected_return=float(snapshot.volatility) * (0.35 if action == "BUY" else -0.35),
            expected_risk=max(float(snapshot.volatility), 0.005),
            trade_probability=confidence,
            confidence_score=confidence,
            decision=action,
            model_version="best_effort_watchlist",
            model_breakdown={"fallback": 1.0},
            reason=f"best-effort live signal fallback after evaluation failure: {type(exc).__name__}",
        )
        alpha_context = AlphaContext()
        alpha_decision = AlphaDecision(
            final_score=max(0.0, float(self.settings.alpha_trade_threshold) - 5.0),
            expected_return=inference.expected_return,
            net_expected_return=inference.expected_return,
            risk_score=min(1.0, inference.expected_risk),
            execution_cost_total=0.0,
            allow_trade=False,
            weights={},
        )
        return SignalResponse(
            symbol=symbol,
            timeframe="multi",
            snapshot=snapshot,
            inference=inference,
            strategy="LOW_CONFIDENCE_WATCHLIST",
            risk_budget=0.0,
            rollout_capital_fraction=1.0,
            alpha=alpha_context,
            alpha_decision=alpha_decision,
        )

    async def evaluate_symbol(self, symbol: str) -> SignalResponse:
        """Builds a probability-based signal and persists it for downstream execution."""
        frames = await self.market_data.fetch_multi_timeframe_ohlcv(symbol)
        order_book = await self.market_data.fetch_order_book(symbol)
        snapshot = self.feature_pipeline.build(symbol, frames, order_book)
        snapshot.features["regime_state"] = self._encode_market_state(snapshot.regime)
        snapshot.features["regime_confidence"] = float(snapshot.regime_confidence)
        if self.strategy_controller is not None:
            self.strategy_controller.record_regime(str(snapshot.regime), float(snapshot.regime_confidence), "system")
        diagnostics = {
            "symbol": symbol,
            "market_data": self._market_data_diagnostics(frames),
            "strategy_candidates": [],
            "rejection_reasons": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await self._inject_sleeve_budget_context(
            user_id="system",
            symbol=symbol,
            snapshot=snapshot,
        )
        strategy_candidates = self.strategy_engine.analyze_all(frames, snapshot=snapshot)
        diagnostics["strategy_candidates"] = [
            {
                "strategy": decision.strategy,
                "signal": decision.signal,
                "confidence": round(float(decision.confidence), 6),
                "reason": str(decision.metadata.get("reason", "")),
                "trade_probability": round(float(decision.metadata.get("trade_success_probability", decision.confidence) or 0.0), 6),
                "regime_type": str(decision.metadata.get("regime_type", snapshot.regime)),
            }
            for decision in strategy_candidates
        ]
        strategy_decision = self.strategy_engine.analyze(frames, snapshot=snapshot)
        diagnostics["selected_strategy"] = {
            "strategy": strategy_decision.strategy,
            "signal": strategy_decision.signal,
            "confidence": round(float(strategy_decision.confidence), 6),
            "reason": str(strategy_decision.metadata.get("reason", "")),
        }
        inference, ai_layer = self._resolve_ai_inference(snapshot, strategy_decision)
        diagnostics["inference"] = {
            "decision": inference.decision,
            "confidence": round(float(inference.confidence_score), 6),
            "trade_probability": round(float(inference.trade_probability), 6),
            "model_version": inference.model_version,
            "reason": inference.reason,
            "ai_layer_mode": ai_layer["mode"],
        }
        probability_features = self._trade_probability_features(snapshot.features, strategy_decision.metadata)
        snapshot.features.update(probability_features)
        if ai_layer["mode"] == "primary":
            effective_inference = self._merge_strategy_signal(inference, strategy_decision)
        else:
            effective_inference = inference
        diagnostics["effective_inference"] = {
            "decision": effective_inference.decision,
            "confidence": round(float(effective_inference.confidence_score), 6),
            "trade_probability": round(float(effective_inference.trade_probability), 6),
            "reason": effective_inference.reason,
        }
        strict_gate = self._strict_trade_gate(
            features=snapshot.features,
            side=effective_inference.decision,
            confidence=effective_inference.confidence_score,
            regime=snapshot.regime,
            volatility=snapshot.volatility,
        )
        snapshot.features.update(
            {
                "strict_trade_score": float(strict_gate["score"]),
                "strict_trade_allowed": 1.0 if strict_gate["allow_trade"] else 0.0,
                "strict_trade_confidence": float(effective_inference.confidence_score),
                "strict_trade_reason": str(strict_gate["reason"]),
            }
        )
        diagnostics["strict_gate"] = strict_gate
        strategy = self.strategy_engine.select(snapshot, effective_inference, frame=frames)
        rollout = self.rollout_manager.status()
        chain_route = self.multi_chain_router.route(symbol, effective_inference.decision, 0.0)
        whale_data = await self.whale_tracker.evaluate_token(symbol, chain_route["chain"], snapshot.features)
        liquidity_data = await self.liquidity_monitor.assess_token(symbol, chain_route["chain"], snapshot.features)
        sentiment_data = await self.sentiment_engine.analyze_token(symbol, snapshot.features)
        security_data = await self.security_scanner.scan_token(symbol, chain_route["chain"], snapshot.features)
        alpha = self._build_alpha_context(
            snapshot=snapshot,
            whale_data=whale_data,
            liquidity_data=liquidity_data,
            sentiment_data=sentiment_data,
            security_data=security_data,
            execution_route=chain_route,
            tax_data=self.tax_engine.estimate_trade_tax(0.0),
            inference_reason=effective_inference.reason,
        )
        alpha_decision = self.alpha_engine.score(
            snapshot=snapshot,
            inference=effective_inference,
            alpha=alpha,
            weight_context={
                "source_metrics": self.performance_tracker.source_metrics(),
                "min_net_profit_threshold": self.settings.min_net_profit_threshold,
            },
            execution_costs=self._execution_costs(chain_route),
        )
        diagnostics["alpha"] = {
            "final_score": round(float(alpha_decision["final_score"]), 6),
            "allow_trade": bool(alpha_decision["allow_trade"]),
            "net_expected_return": round(float(alpha_decision["net_expected_return"]), 6),
        }
        whale_signal = self._whale_direction(alpha)
        whale_conflict_flag = self._whale_conflict(effective_inference.decision, whale_signal)
        self.system_monitor.record_signal(
            whale_veto=whale_conflict_flag,
            blocked_profitable=whale_conflict_flag and alpha_decision["net_expected_return"] > self.settings.min_net_profit_threshold,
        )
        alpha_risk_score = self._alpha_risk_score(alpha)
        account_equity = self.settings.default_portfolio_balance
        spread_bps = self._spread_bps(order_book)
        micro_decision = self.micro_mode_controller.evaluate_signal(
            user_id="system",
            account_equity=account_equity,
            alpha_score=alpha_decision["final_score"],
            whale_conflict=whale_conflict_flag,
            net_expected_return=alpha_decision["net_expected_return"],
            total_cost=alpha_decision["execution_costs"]["total_cost"],
            slippage_bps=min(spread_bps, self.settings.micro_slippage_threshold_bps * 2),
            liquidity_stability=alpha.liquidity.liquidity_stability,
            spread_bps=spread_bps,
            strategy=strategy,
            degraded_mode=self._degraded_mode(),
            volume=float(snapshot.features.get("15m_volume", 0.0)),
        ) if self._is_micro_capital(account_equity) else {"allowed": True, "reasons": []}
        diagnostics["micro"] = {
            "allowed": bool(micro_decision["allowed"]),
            "reasons": list(micro_decision.get("reasons", [])),
        }
        risk = self.risk_engine.evaluate(
            balance=account_equity,
            snapshot=snapshot,
            inference=effective_inference,
            daily_pnl_pct=0.0,
            consecutive_losses=0,
            correlation_to_portfolio=await self._portfolio_correlation(
                user_id="system",
                symbol=symbol,
                features=snapshot.features,
            ),
            alpha_risk_score=alpha_risk_score,
            hours_since_rebalance=self._hours_since_rebalance(),
            trade_intelligence_metrics=self._trade_intelligence_metrics(strategy_decision.metadata),
        )
        diagnostics["risk"] = {
            "risk_budget": round(float(risk.risk_budget), 6),
            "rebalance_required": bool(risk.rebalance_required),
        }
        if whale_conflict_flag or not alpha_decision["allow_trade"] or alpha_decision["final_score"] <= self.settings.alpha_trade_threshold:
            strategy = "NO_TRADE"
        if whale_conflict_flag:
            diagnostics["rejection_reasons"].append("whale_conflict")
        if not alpha_decision["allow_trade"]:
            diagnostics["rejection_reasons"].append("alpha_engine_rejected")
        if alpha_decision["final_score"] <= self.settings.alpha_trade_threshold:
            diagnostics["rejection_reasons"].append("alpha_score_below_threshold")
        if self._degraded_mode():
            strategy = "NO_TRADE"
            diagnostics["rejection_reasons"].append("degraded_mode")
        if not micro_decision["allowed"]:
            strategy = "NO_TRADE"
            diagnostics["rejection_reasons"].extend([f"micro:{reason}" for reason in micro_decision.get("reasons", [])])
        if not strict_gate["allow_trade"]:
            strategy = "NO_TRADE"
            diagnostics["rejection_reasons"].append(f"strict_gate:{strict_gate['reason_code']}")
        meta_decision = None
        if self.meta_controller is not None:
            meta_decision = self.meta_controller.govern_signal(
                user_id="system",
                symbol=symbol,
                side=effective_inference.decision,
                proposed_strategy=strategy,
                volatility=snapshot.volatility,
                macro_bias=self.cache.get_json("macro:global_bias") or {},
                liquidity_stability=alpha.liquidity.liquidity_stability,
                latency_ms=float(self.cache.get("monitor:execution_latency_ms") or 0.0),
                ai_score=alpha_decision["final_score"],
                ai_confidence=effective_inference.confidence_score,
                whale_score=alpha.whale.score,
                sentiment_score=alpha.sentiment.hype_score,
                regime_type=strategy_decision.metadata.get("regime_type", snapshot.regime),
                trade_intelligence_metrics=self._trade_intelligence_metrics(strategy_decision.metadata),
            )
            if not meta_decision.allow_trade:
                strategy = "NO_TRADE"
                diagnostics["rejection_reasons"].extend([f"meta:{reason}" for reason in meta_decision.reasons])
            diagnostics["meta"] = {
                "allow_trade": bool(meta_decision.allow_trade),
                "confidence": round(float(meta_decision.confidence_score), 6),
                "strategy": meta_decision.selected_strategy,
                "reasons": list(meta_decision.reasons),
            }
        risk_budget = risk.risk_budget * rollout.capital_fraction
        if meta_decision is not None:
            risk_budget *= meta_decision.capital_multiplier
        trade_direction = self._final_signal_action(snapshot, effective_inference, strategy_decision)
        final_confidence = max(
            float(strategy_decision.metadata.get("adjusted_confidence", strategy_decision.confidence) or 0.0),
            float(effective_inference.confidence_score),
        )
        force_override_active = self._force_execution_override_active(final_confidence)
        if force_override_active and strategy == "NO_TRADE" and trade_direction in {"BUY", "SELL"}:
            diagnostics["force_execution_override"] = {
                "active": True,
                "confidence_floor": float(self.settings.force_execution_override_confidence_floor),
                "original_rejection_reasons": list(diagnostics["rejection_reasons"]),
            }
            strategy = "FORCED_PAPER_TRADE"
            diagnostics["rejection_reasons"].append("force_execution_override")
        final_action = "HOLD" if strategy == "NO_TRADE" else trade_direction
        accepted_trade = strategy != "NO_TRADE" and final_action in {"BUY", "SELL"}
        rejection_reason = "; ".join(dict.fromkeys(diagnostics["rejection_reasons"])) or None
        low_confidence = (
            not force_override_active
            and (strategy == "NO_TRADE" or final_confidence < max(self.settings.signal_min_publish_confidence, 0.4))
        )
        published_strategy = strategy if strategy != "NO_TRADE" else "LOW_CONFIDENCE_WATCHLIST"
        payload = {
            "symbol": symbol,
            "signal_id": f"{symbol}:{int(datetime.now(timezone.utc).timestamp())}",
            "price": snapshot.price,
            "regime": snapshot.regime,
            "strategy_regime": strategy_decision.metadata.get("regime_type", snapshot.regime),
            "adjusted_strategy_confidence": strategy_decision.metadata.get("adjusted_confidence", strategy_decision.confidence),
            "volatility": snapshot.volatility,
            "inference": effective_inference.model_dump(),
            "strategy": published_strategy,
            "action": final_action,
            "confidence": round(float(final_confidence), 6),
            "risk_budget": risk_budget,
            "reason": effective_inference.reason,
            "feature_snapshot": snapshot.features,
            "strict_trade_gate": strict_gate,
            "atr": snapshot.atr,
            "regime_confidence": snapshot.regime_confidence,
            "expected_return": effective_inference.expected_return,
            "expected_risk": effective_inference.expected_risk,
            "model_version": effective_inference.model_version,
            "rollout_capital_fraction": rollout.capital_fraction,
            "alpha": alpha.model_dump(),
            "alpha_decision": alpha_decision,
            "whale_conflict_flag": whale_conflict_flag,
            "whale_signal": whale_signal,
            "chain_route": chain_route,
            "rebalance_required": risk.rebalance_required,
            "decision_reason": self._decision_reason(inference.decision, whale_signal, whale_conflict_flag, alpha_decision),
            "degraded_mode": self._degraded_mode(),
            "micro_decision": micro_decision,
            "required_tier": self._required_tier(alpha_decision["final_score"]),
            "min_balance": self._minimum_balance_requirement(alpha_decision["final_score"]),
            "rejection_reason": rejection_reason,
            "low_confidence": low_confidence,
            "final_trade_status": "accepted" if accepted_trade else "rejected",
            "allowed_risk_profiles": self._allowed_risk_profiles(snapshot.regime, snapshot.volatility),
            "meta_control": meta_decision.payload() if meta_decision is not None else None,
            "strategy_signal": strategy_decision.signal,
            "strategy_confidence": strategy_decision.confidence,
            "strategy_name": strategy_decision.strategy,
            "strategy_metadata": strategy_decision.metadata,
            "trade_success_probability": strategy_decision.metadata.get(
                "trade_success_probability",
                effective_inference.trade_probability,
            ),
            "raw_trade_success_probability": strategy_decision.metadata.get(
                "raw_trade_success_probability",
                strategy_decision.metadata.get("trade_success_probability", effective_inference.trade_probability),
            ),
            "trade_probability_features": probability_features,
            "factor_sleeve_budget_delta": snapshot.features.get("factor_sleeve_budget_delta", 0.0),
            "factor_sleeve_recent_win_rate": snapshot.features.get("factor_sleeve_recent_win_rate", 0.5),
            "factor_sleeve_budget_turnover": snapshot.features.get("factor_sleeve_budget_turnover", 0.0),
            "max_factor_sleeve_budget_gap_pct": snapshot.features.get("max_factor_sleeve_budget_gap_pct", 0.0),
            "ai_layer_mode": ai_layer["mode"],
            "ai_layer_disabled": ai_layer["disabled"],
            "ai_fallback_reason": ai_layer["reason"],
            "forced_execution_override": force_override_active and accepted_trade,
            "pipeline_diagnostics": diagnostics,
        }
        if low_confidence:
            payload["required_tier"] = "free"
            payload["min_balance"] = 0.0
        broadcast_payload = self.signal_broadcaster.publish_signal(payload)
        self._store_signal_diagnostics(symbol, diagnostics={**diagnostics, "action": final_action, "confidence": round(float(final_confidence), 6), "accepted_trade": accepted_trade, "rejection_reason": rejection_reason, "low_confidence": low_confidence})
        self._safe_firestore_call("save_signal", broadcast_payload)
        self._safe_firestore_call(
            "save_performance_snapshot",
            "whale_veto",
            {
                "total_signals": int(self.cache.get("monitor:total_signals") or 0),
                "whale_veto_blocked": int(self.cache.get("monitor:whale_veto_blocked") or 0),
                "blocked_profitable_signals": int(self.cache.get("monitor:blocked_profitable_signals") or 0),
                "veto_efficiency_ratio": self.system_monitor._veto_efficiency_ratio(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        self._safe_firestore_call(
            "save_performance_snapshot",
            "signal_distribution",
            {
                "symbol": symbol,
                "signal_version": broadcast_payload["signal_version"],
                **broadcast_payload["distribution"],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        self._safe_firestore_call("save_liquidity_snapshot", {"symbol": symbol, **liquidity_data})
        self._safe_firestore_call("save_sentiment_snapshot", {"symbol": symbol, **sentiment_data})
        self._safe_firestore_call("save_security_scan", {"symbol": symbol, **security_data})
        if whale_data["new_token_entry"]:
            self._safe_firestore_call("save_whale_event", {"symbol": symbol, **whale_data, "trigger_auto_trade": self.settings.auto_trade_on_whale_signal})
        return SignalResponse(
            symbol=symbol,
            timeframe="multi",
            snapshot=snapshot,
            inference=effective_inference,
            strategy=published_strategy,
            risk_budget=risk_budget,
            rollout_capital_fraction=rollout.capital_fraction,
            alpha=alpha,
            alpha_decision=AlphaDecision(**{k: alpha_decision[k] for k in AlphaDecision.model_fields}),
        )

    def _resolve_ai_inference(self, snapshot: FeatureSnapshot, strategy_decision) -> tuple[AIInference, dict[str, object]]:
        if self._ai_layer_disabled():
            return self._rule_based_inference(
                snapshot,
                strategy_decision,
                fallback_reason="ai_layer_disabled",
            ), {
                "mode": "rule_based",
                "disabled": True,
                "reason": "ai_layer_disabled",
            }

        try:
            inference = self.ai_engine.infer(snapshot)
        except Exception as exc:
            self._disable_ai_layer(str(exc))
            logger.exception(
                "ai_inference_failed",
                extra={"event": "ai_inference_failed", "context": {"error": str(exc)}},
            )
            return self._rule_based_inference(
                snapshot,
                strategy_decision,
                fallback_reason="ai_model_failure",
            ), {
                "mode": "rule_based",
                "disabled": True,
                "reason": "ai_model_failure",
            }

        if inference.confidence_score < self.settings.ai_fallback_confidence_threshold:
            logger.warning(
                "ai_low_confidence_fallback",
                extra={
                    "event": "ai_low_confidence_fallback",
                    "context": {
                        "confidence": round(float(inference.confidence_score), 6),
                        "threshold": round(float(self.settings.ai_fallback_confidence_threshold), 6),
                        "strategy_signal": strategy_decision.signal,
                    },
                },
            )
            return self._rule_based_inference(
                snapshot,
                strategy_decision,
                fallback_reason="ai_low_confidence",
                source_inference=inference,
            ), {
                "mode": "rule_based",
                "disabled": False,
                "reason": "ai_low_confidence",
            }

        return inference, {
            "mode": "primary",
            "disabled": False,
            "reason": "",
        }

    def _merge_strategy_signal(self, inference, strategy_decision):
        success_probability = float(
            strategy_decision.metadata.get(
                "trade_success_probability",
                strategy_decision.metadata.get("adjusted_confidence", strategy_decision.confidence),
            )
        )
        adjusted_confidence = float(
            strategy_decision.metadata.get("adjusted_confidence", strategy_decision.confidence)
        )
        should_override = (
            strategy_decision.signal != "HOLD"
            and (
                inference.decision == "HOLD"
                or adjusted_confidence >= max(inference.confidence_score, 0.55)
            )
        )
        if not should_override:
            return inference
        combined_confidence = max(inference.confidence_score, adjusted_confidence)
        return inference.model_copy(
            update={
                "decision": strategy_decision.signal,
                "trade_probability": max(combined_confidence, success_probability),
                "confidence_score": combined_confidence,
                "reason": f"{inference.reason} | strategy:{strategy_decision.strategy}",
            }
        )

    def _trade_intelligence_metrics(self, metadata: dict | None) -> dict[str, float]:
        details = metadata or {}
        win_rate = details.get("meta_model_regime_win_rate", details.get("win_rate"))
        avg_r_multiple = details.get("meta_model_avg_r_multiple", details.get("avg_r_multiple"))
        avg_drawdown = details.get("meta_model_avg_drawdown", details.get("avg_drawdown"))
        metrics: dict[str, float] = {}
        if win_rate is not None:
            metrics["win_rate"] = float(win_rate)
        if avg_r_multiple is not None:
            metrics["avg_r_multiple"] = float(avg_r_multiple)
        if avg_drawdown is not None:
            metrics["avg_drawdown"] = float(avg_drawdown)
        return metrics

    async def execute_signal(self, request: TradeRequest) -> TradeResponse:
        if request.order_type == "LIMIT" and request.limit_price is None:
            raise ValueError("limit_price is required for LIMIT orders")
        normalized_signal_id = str(request.signal_id or "").strip() or None
        if normalized_signal_id != request.signal_id:
            request = request.model_copy(update={"signal_id": normalized_signal_id})
        signal_lock_key: str | None = None
        meta_decision = None
        order_submitted = False
        recovery_state_persisted = False
        force_override_active = self._force_execution_override_active(request.confidence)
        if request.signal_id:
            signal_lock_key = f"signal:lock:{request.signal_id}"
            cached_response = await self._claim_signal(request.signal_id, request.symbol, request.side)
            if cached_response is not None:
                self.system_monitor.increment_duplicate()
                return TradeResponse(**cached_response)
        try:
            latest_price = await self.market_data.fetch_latest_price(request.symbol)
            self._publish_activity(
                status="analyzing",
                message=f"{request.symbol.upper()} under validation",
                bot_state="ANALYZING",
                symbol=request.symbol,
                confidence=float(request.confidence),
                intent=f"Validating {request.symbol.upper()} before execution",
                readiness=max(70.0, min(100.0, float(request.feature_snapshot.get('strict_trade_score', 70.0) or 70.0))),
                confidence_building=True,
                reason=str(request.feature_snapshot.get("strict_trade_reason", "execution checks in progress")),
            )
            quantity = request.quantity or (request.requested_notional or 0.0) / max(latest_price, 1e-8)
            if quantity <= 0:
                raise ValueError("quantity or requested_notional is required")
            drawdown_status = self.drawdown_protection.load(request.user_id)
            protection_controls = self.drawdown_protection.load_controls(request.user_id)
            risk_profile = self.risk_controller.profile(request.user_id) if self.risk_controller is not None else None
            account_equity = drawdown_status.current_equity
            if drawdown_status.state in {"PAUSED", "COOLDOWN"}:
                raise ValueError("Trading is paused by drawdown protection")
            if protection_controls.emergency_stop_active:
                raise ValueError(f"Trading is paused by emergency stop: {protection_controls.emergency_stop_reason or 'manual'}")
            if self._degraded_mode():
                raise ValueError("Trading is paused because execution latency is degraded")
            effective_confidence_floor = float(
                risk_profile.confidence_floor
                if risk_profile is not None
                else self.settings.strict_trade_confidence_floor
            )
            if float(request.confidence) < effective_confidence_floor and not force_override_active:
                raise ValueError("Trade confidence is below the strict execution floor")
            if risk_profile is not None and risk_profile.allowed_symbols:
                if request.symbol.upper() not in set(risk_profile.allowed_symbols):
                    raise ValueError(f"Risk profile {risk_profile.level} blocks {request.symbol.upper()}")
            if not request.alpha_context.security.tradable and not force_override_active:
                raise ValueError("Security scanner blocked trade")
            whale_signal = self._whale_direction(request.alpha_context)
            if self._whale_conflict(request.side, whale_signal) and not force_override_active:
                raise ValueError("Whale tracker vetoed conflicting trade")
            rollout = self.rollout_manager.status()
            capital_multiplier = self.drawdown_protection.capital_multiplier(request.user_id) * rollout.capital_fraction
            if capital_multiplier <= 0:
                raise ValueError("Capital protection disabled trading")
            macro_bias = self._macro_bias_payload(request)
            requested_notional = request.requested_notional or latest_price * quantity
            route = self.multi_chain_router.route(
                request.symbol,
                request.side,
                requested_notional,
            )
            order_book = await self.market_data.fetch_order_book(request.symbol)
            spread_bps = self._spread_bps(order_book)
            portfolio_summary = (
                await self.portfolio_ledger.portfolio_concentration_profile(
                    request.user_id,
                    candidate_symbol=request.symbol,
                )
                if self.portfolio_ledger is not None
                else {
                    "gross_exposure_pct": 0.0,
                    "symbol_exposures": {},
                }
            )
            self.system_monitor.update_portfolio_concentration(portfolio_summary)
            effective_max_active_trades = int(
                risk_profile.max_active_trades
                if risk_profile is not None
                else self.settings.max_active_trades
            )
            if int(portfolio_summary.get("active_trades", 0) or 0) >= effective_max_active_trades:
                raise RiskLimitExceededError(
                    "Maximum active trades reached",
                    error_code="MAX_ACTIVE_TRADES_REACHED",
                    details={"max_active_trades": effective_max_active_trades},
                )
            if float((portfolio_summary.get("symbol_exposure_pct") or {}).get(request.symbol.upper(), 0.0) or 0.0) > 0.0:
                raise RiskLimitExceededError(
                    "An active trade already exists for this symbol",
                    error_code="DUPLICATE_ACTIVE_SYMBOL",
                    details={"symbol": request.symbol.upper()},
                )
            active_trades = [
                trade
                for trade in self.redis_state_manager.restore_active_trades()
                if str(trade.get("user_id", "") or "") == request.user_id
            ]
            portfolio_correlation = await self._portfolio_correlation(
                user_id=request.user_id,
                symbol=request.symbol,
                features=request.feature_snapshot,
            )
            symbol_score = float(request.feature_snapshot.get("factor_sleeve_recent_win_rate", 0.5) or 0.5)
            if self._symbol_allocation_multiplier(request.symbol) > 1.0:
                symbol_score = max(symbol_score, 0.65)
            portfolio_risk_fraction = float(self.settings.portfolio_base_risk_per_trade)
            portfolio_risk_multiplier = 1.0
            portfolio_assessment = {
                "allow_trade": True,
                "risk_fraction": portfolio_risk_fraction,
                "multiplier": portfolio_risk_multiplier,
                "reason": "",
                "correlated_count": 0,
                "correlation_risk": round(float(portfolio_correlation), 8),
            }
            if self.portfolio_manager is not None:
                portfolio_risk_fraction = self.portfolio_manager.compute_allocation(
                    confidence=float(request.confidence),
                    regime=str(request.feature_snapshot.get("regime", request.feature_snapshot.get("regime_type", "RANGING"))),
                    symbol_score=symbol_score,
                    drawdown_pct=float(drawdown_status.rolling_drawdown),
                )
                portfolio_assessment = self.portfolio_manager.assess_new_trade(
                    active_trades=active_trades,
                    symbol=request.symbol,
                    side=request.side,
                    proposed_risk_fraction=portfolio_risk_fraction,
                    gross_exposure_pct=float(portfolio_summary.get("gross_exposure_pct", 0.0) or 0.0),
                    correlation_to_portfolio=portfolio_correlation,
                )
                if not portfolio_assessment["allow_trade"]:
                    raise ValueError(portfolio_assessment["reason"] or "Portfolio intelligence blocked trade")
                portfolio_risk_fraction = float(portfolio_assessment["risk_fraction"])
                portfolio_risk_multiplier = portfolio_risk_fraction / max(float(self.settings.portfolio_base_risk_per_trade), 1e-8)
            if risk_profile is not None:
                portfolio_risk_fraction = min(float(portfolio_risk_fraction), float(risk_profile.risk_fraction))
                portfolio_risk_multiplier = portfolio_risk_fraction / max(float(self.settings.portfolio_base_risk_per_trade), 1e-8)
            request.feature_snapshot.update(
                {
                    "portfolio_risk_fraction": float(portfolio_risk_fraction),
                    "portfolio_risk_multiplier": float(portfolio_risk_multiplier),
                    "portfolio_correlation_risk": float(portfolio_assessment.get("correlation_risk", portfolio_correlation)),
                    "portfolio_correlated_count": float(portfolio_assessment.get("correlated_count", 0)),
                    "portfolio_drawdown": float(drawdown_status.rolling_drawdown),
                }
            )
            strict_gate = self._strict_trade_gate(
                features=request.feature_snapshot,
                side=request.side,
                confidence=request.confidence,
                regime=str(request.feature_snapshot.get("regime", request.feature_snapshot.get("regime_type", "RANGING"))),
                volatility=float(request.feature_snapshot.get("volatility", request.expected_risk or 0.0)),
                confidence_floor_override=effective_confidence_floor,
            )
            if not strict_gate["allow_trade"] and not force_override_active:
                raise ValueError(f"Strict trade gate rejected trade: {strict_gate['reason']}")
            if force_override_active and not strict_gate["allow_trade"]:
                request.feature_snapshot["forced_execution_override"] = 1.0
            if hasattr(self.model_stability, "update_concentration_state"):
                self.model_stability.update_concentration_state(portfolio_summary)
            self._apply_portfolio_context_to_feature_snapshot(
                feature_snapshot=request.feature_snapshot,
                portfolio_summary=portfolio_summary,
                symbol=request.symbol,
            )
            if self.meta_controller is not None:
                meta_decision = self.meta_controller.govern_signal(
                    user_id=request.user_id,
                    symbol=request.symbol,
                    side=request.side,
                    proposed_strategy=request.strategy or "AI",
                    volatility=float(request.feature_snapshot.get("volatility", request.expected_risk or 0.0)),
                    macro_bias=macro_bias,
                    liquidity_stability=request.alpha_context.liquidity.liquidity_stability,
                    latency_ms=float(self.cache.get("monitor:execution_latency_ms") or 0.0),
                    ai_score=request.alpha_decision.final_score or request.confidence * 100,
                    ai_confidence=request.confidence,
                    whale_score=request.alpha_context.whale.score,
                    sentiment_score=request.alpha_context.sentiment.hype_score,
                    regime_type=str(request.feature_snapshot.get("regime_type", request.feature_snapshot.get("regime", "RANGING"))),
                    trade_intelligence_metrics=self._trade_intelligence_metrics(request.feature_snapshot),
                )
                if not meta_decision.allow_trade and not force_override_active:
                    blocked_trade_id = request.signal_id or f"blocked:{request.symbol}:{int(datetime.now(timezone.utc).timestamp())}"
                    self.meta_controller.log_blocked_trade(
                        trade_id=blocked_trade_id,
                        user_id=request.user_id,
                        symbol=request.symbol,
                        proposed_strategy=request.strategy or "AI",
                        reason=", ".join(meta_decision.reasons),
                        signals={
                            "ai_score": request.alpha_decision.final_score or request.confidence * 100,
                            "whale_score": request.alpha_context.whale.score,
                            "sentiment_score": request.alpha_context.sentiment.hype_score,
                            "macro_bias": macro_bias,
                            "confidence": meta_decision.confidence_score,
                        },
                        conflicts=meta_decision.reasons,
                    )
                    raise ValueError(f"Meta controller blocked trade: {', '.join(meta_decision.reasons)}")
            micro_validation = self.micro_mode_controller.evaluate_signal(
                user_id=request.user_id,
                account_equity=account_equity,
                alpha_score=request.alpha_decision.final_score,
                whale_conflict=self._whale_conflict(request.side, whale_signal),
                net_expected_return=request.alpha_decision.net_expected_return or (request.expected_return or 0.0),
                total_cost=request.alpha_decision.execution_cost_total,
                slippage_bps=spread_bps,
                liquidity_stability=request.alpha_context.liquidity.liquidity_stability,
                spread_bps=spread_bps,
                strategy=request.strategy or "TREND_FOLLOW",
                degraded_mode=self._degraded_mode(),
                volume=float(request.feature_snapshot.get("15m_volume", 0.0)),
            ) if self._is_micro_capital(account_equity) else {"allowed": True, "reasons": []}
            if not micro_validation["allowed"]:
                raise ValueError(f"Micro mode rejected trade: {','.join(micro_validation['reasons'])}")
            meta_capital_multiplier = meta_decision.capital_multiplier if meta_decision is not None else 1.0
            if force_override_active and meta_decision is not None and not meta_decision.allow_trade:
                meta_capital_multiplier = 1.0
            effective_capital_multiplier = capital_multiplier * meta_capital_multiplier
            adaptive_config = self._adaptive_strategy_config()
            effective_capital_multiplier *= float(adaptive_config.get("capital_allocation_multiplier", 1.0) or 1.0)
            effective_capital_multiplier *= self._symbol_allocation_multiplier(request.symbol)
            effective_capital_multiplier *= portfolio_risk_multiplier
            size_plan = self.micro_mode_controller.determine_trade_size(
                user_id=request.user_id,
                account_equity=account_equity,
                latest_price=latest_price,
                requested_notional=requested_notional * effective_capital_multiplier * macro_bias["multiplier"],
                slippage_bps=spread_bps,
            ) if self._is_micro_capital(account_equity) else {
                "skip": False,
                "trade_notional": requested_notional * effective_capital_multiplier * macro_bias["multiplier"],
                "quantity": quantity * effective_capital_multiplier * macro_bias["multiplier"],
                "mode": "standard",
            }
            if size_plan["skip"]:
                raise ValueError(size_plan["reason"])
            capped_notional = self.risk_engine.enforce_user_controls(
                balance=account_equity,
                requested_notional=float(size_plan["trade_notional"]),
                daily_pnl_pct=self.drawdown_protection.daily_pnl_pct(request.user_id),
                max_capital_allocation_pct=protection_controls.max_capital_allocation_pct,
                daily_loss_limit_override=protection_controls.daily_loss_limit,
                emergency_stop_active=protection_controls.emergency_stop_active,
            )
            if capped_notional <= 0:
                raise ValueError("User protection controls reduced trade allocation to zero")
            current_symbol_exposure = float(
                (portfolio_summary.get("symbol_exposures") or {}).get(request.symbol.upper(), 0.0)
            ) / max(account_equity, 1e-8)
            current_side_exposure = float(
                (portfolio_summary.get("side_exposure_pct") or {}).get(request.side.upper(), 0.0)
            )
            current_theme_exposure = float(
                portfolio_summary.get("candidate_theme_exposure_pct", 0.0)
            )
            current_cluster_exposure = float(portfolio_summary.get("candidate_cluster_exposure_pct", 0.0))
            current_beta_bucket_exposure = float(portfolio_summary.get("candidate_beta_bucket_exposure_pct", 0.0))
            capped_notional = self.risk_engine.enforce_portfolio_controls(
                balance=account_equity,
                requested_notional=capped_notional,
                current_portfolio_exposure_pct=float(portfolio_summary.get("gross_exposure_pct", 0.0)),
                correlation_to_portfolio=portfolio_correlation,
                current_symbol_exposure_pct=current_symbol_exposure,
                side=request.side,
                current_side_exposure_pct=current_side_exposure,
                current_theme_exposure_pct=current_theme_exposure,
                current_cluster_exposure_pct=current_cluster_exposure,
                current_beta_bucket_exposure_pct=current_beta_bucket_exposure,
                sleeve_budget_turnover=float(portfolio_summary.get("factor_sleeve_budget_turnover", 0.0) or 0.0),
                sleeve_budget_gap_pct=float(portfolio_summary.get("max_factor_sleeve_budget_gap_pct", 0.0) or 0.0),
            )
            size_plan["trade_notional"] = capped_notional
            size_plan["quantity"] = capped_notional / max(latest_price, 1e-8)
            quantity = size_plan["quantity"]
            self._validate_trade_safety(
                symbol=request.symbol,
                side=request.side,
                quantity=quantity,
                latest_price=latest_price,
                order_book=order_book,
                request=request,
            )
            self._publish_activity(
                status="opportunity_found",
                message=f"{request.symbol.upper()} passed validation -> submitting order",
                bot_state="EXECUTING",
                symbol=request.symbol,
                confidence=float(request.confidence),
                action="Executing trade",
            )
            shard_id = self.shard_manager.shard_id(request.user_id)
            execution_priority = self.shard_manager.queue_priority(
                {
                    "alpha_decision": request.alpha_decision.model_dump(),
                    "trade_success_probability": float(
                        request.feature_snapshot.get("trade_success_probability", request.confidence)
                    ),
                    "raw_trade_success_probability": float(
                        request.feature_snapshot.get(
                            "raw_trade_success_probability",
                            request.feature_snapshot.get("trade_success_probability", request.confidence),
                        )
                    ),
                    "factor_sleeve_budget_delta": float(request.feature_snapshot.get("factor_sleeve_budget_delta", 0.0) or 0.0),
                    "factor_sleeve_recent_win_rate": float(request.feature_snapshot.get("factor_sleeve_recent_win_rate", 0.5) or 0.0),
                    "factor_sleeve_budget_turnover": float(request.feature_snapshot.get("factor_sleeve_budget_turnover", 0.0) or 0.0),
                    "max_factor_sleeve_budget_gap_pct": float(request.feature_snapshot.get("max_factor_sleeve_budget_gap_pct", 0.0) or 0.0),
                },
                {"user_id": request.user_id, "tier": "vip", "risk_profile": "moderate"},
            )
            scheduled_delay_ms = self.execution_queue_manager._random_delay_ms(execution_priority)
            order = await self._submit_order(
                symbol=request.symbol,
                side=request.side,
                quantity=quantity,
                order_type=request.order_type,
                limit_price=request.limit_price,
                order_book=order_book,
                queue_context={
                    "shard_id": shard_id,
                    "priority": execution_priority,
                    "scheduled_delay_ms": scheduled_delay_ms,
                },
            )
            executed_price = float(
                order.get("fills", [{}])[0].get("price") or order.get("price") or 0.0
            )
            stop_loss, trailing_stop_pct, take_profit = self._macro_adjusted_exit_levels(
                side=request.side,
                executed_price=executed_price,
                expected_return=request.expected_return or 0.0,
                macro_bias=macro_bias,
                feature_snapshot=request.feature_snapshot,
            )
            response = TradeResponse(
                trade_id=str(order["orderId"]),
                status=order["status"],
                trading_mode=self.settings.trading_mode,
                symbol=request.symbol,
                side=request.side,
                executed_price=executed_price,
                executed_quantity=float(order.get("executedQty", quantity)),
                stop_loss=stop_loss,
                trailing_stop_pct=trailing_stop_pct,
                take_profit=take_profit,
                fee_paid=float(order.get("feePaid", 0.0)),
                slippage_bps=float(order.get("slippageBps", self.settings.slippage_bps)),
                filled_ratio=float(order.get("filledRatio", 1.0)),
                rollout_capital_fraction=rollout.capital_fraction,
                explanation=self._human_explanation(request, route, macro_bias),
                alpha_score=request.alpha_decision.final_score,
                macro_bias_multiplier=macro_bias["multiplier"],
                macro_bias_regime=macro_bias["regime"],
            )
            order_submitted = True
            executed_notional = response.executed_price * response.executed_quantity
            self._persist_opening_recovery_state(
                request=request,
                response=response,
                route=route,
                quantity=response.executed_quantity,
                requested_notional=size_plan["trade_notional"],
            )
            recovery_state_persisted = True
            self._persist_active_trade_details(
                request=request,
                response=response,
                route=route,
                meta_decision=meta_decision,
                spread_bps=spread_bps,
                executed_notional=executed_notional,
                execution_priority=execution_priority,
                scheduled_delay_ms=scheduled_delay_ms,
                shard_id=shard_id,
                execution_latency_ms=float(order.get("executionLatencyMs", route.get("routing_latency_ms", 0.0))),
            )
            if request.signal_id:
                self._store_signal_response(request.signal_id, response)
            self.micro_mode_controller.record_trade_open(request.user_id)
            self.system_monitor.record_execution(
                latency_ms=float(order.get("executionLatencyMs", route.get("routing_latency_ms", 0.0))),
                slippage_bps=response.slippage_bps,
            )
            self.system_monitor.record_api_call(success=True)
            tax_estimate = self.tax_engine.estimate_trade_tax(
                profit=(request.expected_return or 0.0) * executed_notional
            )
            self._safe_firestore_call(
                "save_trade",
                {
                    "trade_id": response.trade_id,
                    "user_id": request.user_id,
                    "symbol": request.symbol,
                    "side": request.side,
                    "entry": response.executed_price,
                    "executed_quantity": response.executed_quantity,
                    "executed_notional": executed_notional,
                    "exit": None,
                    "profit": None,
                    "ai_confidence": request.confidence,
                    "reason": request.reason,
                    "status": response.status,
                    "trading_mode": self.settings.trading_mode,
                    "stop_loss": response.stop_loss,
                    "trailing_stop_pct": response.trailing_stop_pct,
                    "take_profit": response.take_profit,
                    "fee_paid": response.fee_paid,
                    "slippage_bps": response.slippage_bps,
                    "filled_ratio": response.filled_ratio,
                    "expected_return": request.expected_return,
                    "expected_risk": request.expected_risk,
                    "features": request.feature_snapshot,
                    "regime": str(request.feature_snapshot.get("regime", request.feature_snapshot.get("regime_type", "RANGING"))).upper(),
                    "signal_id": request.signal_id,
                    "rollout_capital_fraction": rollout.capital_fraction,
                    "entry_reason": request.reason,
                    "exit_reason": "",
                    "max_profit": 0.0,
                    "exit_type": "",
                    "risk_fraction": float(portfolio_risk_fraction),
                    "portfolio_correlation_risk": float(portfolio_assessment.get("correlation_risk", portfolio_correlation)),
                    "alpha": request.alpha_context.model_dump(),
                    "alpha_decision": request.alpha_decision.model_dump(),
                    "chain_route": route,
                    "explanation": response.explanation,
                    "alpha_score": response.alpha_score,
                    "whale_signal": whale_signal,
                    "risk_level": request.alpha_context.explainability.risk_summary,
                    "execution_latency_ms": float(order.get("executionLatencyMs", route.get("routing_latency_ms", 0.0))),
                    "micro_mode": self._is_micro_capital(account_equity),
                    "micro_trade_mode": size_plan["mode"],
                    "macro_bias_multiplier": macro_bias["multiplier"],
                    "macro_bias_regime": macro_bias["regime"],
                    "macro_take_profit": take_profit,
                    "execution_shard": shard_id,
                    "execution_priority": execution_priority,
                    "scheduled_delay_ms": scheduled_delay_ms,
                    "requested_notional": size_plan["trade_notional"],
                    "meta_strategy": meta_decision.selected_strategy if meta_decision is not None else request.strategy,
                    "meta_confidence_score": meta_decision.confidence_score if meta_decision is not None else request.confidence,
                    "meta_capital_multiplier": meta_decision.capital_multiplier if meta_decision is not None else 1.0,
                    "meta_health_ok": meta_decision.health.healthy if meta_decision is not None else True,
                    **tax_estimate,
                },
                swallow_exceptions=False,
            )
            self.cache.publish("trades", json.dumps({"trade_id": response.trade_id, "symbol": request.symbol, "status": response.status}))
            if self.meta_controller is not None and meta_decision is not None:
                self.meta_controller.log_decision(
                    trade_id=response.trade_id,
                    user_id=request.user_id,
                    symbol=request.symbol,
                    decision=meta_decision,
                    signals={
                        "ai_score": request.alpha_decision.final_score or request.confidence * 100,
                        "ai_confidence": request.confidence,
                        "whale_score": request.alpha_context.whale.score,
                        "sentiment_score": request.alpha_context.sentiment.hype_score,
                        "macro_bias": macro_bias,
                    },
                    conflicts=meta_decision.reasons,
                    risk_adjustments={
                        "drawdown_capital_multiplier": capital_multiplier,
                        "meta_capital_multiplier": meta_decision.capital_multiplier,
                        "macro_bias_multiplier": macro_bias["multiplier"],
                        "effective_trade_notional": executed_notional,
                    },
                    reason=response.explanation,
                )
            self.firestore.save_training_sample(
                {
                    "sample_id": response.trade_id,
                    "trade_id": response.trade_id,
                    "user_id": request.user_id,
                    "symbol": request.symbol,
                    "features": request.feature_snapshot,
                    "probability_features": self._extract_probability_features(request.feature_snapshot),
                    "expected_return": request.expected_return,
                    "expected_risk": request.expected_risk,
                    "confidence": request.confidence,
                    "trading_mode": self.settings.trading_mode,
                    "outcome": None,
                    "alpha": request.alpha_context.model_dump(),
                    "alpha_decision": request.alpha_decision.model_dump(),
                    "micro_mode": self._is_micro_capital(account_equity),
                    "execution_shard": shard_id,
                    "execution_priority": execution_priority,
                }
            )
            self.firestore.save_tax_record(
                {
                    "trade_id": response.trade_id,
                    "user_id": request.user_id,
                    "symbol": request.symbol,
                    **tax_estimate,
                }
            )
            if self.portfolio_ledger is not None:
                self.portfolio_ledger.record_trade_open(
                    user_id=request.user_id,
                    trade_id=response.trade_id,
                    symbol=request.symbol,
                    side=request.side,
                    entry_price=response.executed_price,
                    executed_quantity=response.executed_quantity,
                    notional=executed_notional,
                    fee_paid=response.fee_paid,
                )
            current_active = int(self.cache.get("position:active_count") or 0) + 1
            self.cache.set("position:active_count", str(current_active), ttl=self.settings.monitor_state_ttl_seconds)
            self.system_monitor.set_active_trades(current_active)
            if self.meta_controller is not None:
                self.meta_controller.record_trade_open(
                    user_id=request.user_id,
                    symbol=request.symbol,
                    notional=size_plan["trade_notional"],
                )
            self._log_trade_recorded(
                trade_id=response.trade_id,
                symbol=request.symbol,
                side=request.side,
            )
            self._publish_activity(
                status="executed",
                message=f"{request.symbol.upper()} trade executed",
                bot_state="EXECUTING",
                symbol=request.symbol,
                confidence=float(request.confidence),
                action=response.status,
                intent=f"Managing live {request.symbol.upper()} position",
                readiness=100.0,
                confidence_building=True,
                reason="Trade passed all execution gates",
                extra={"trade_id": response.trade_id},
            )
            return response
        except Exception as exc:
            self.system_monitor.increment_error()
            self.system_monitor.record_api_call(success=False)
            if signal_lock_key is not None and not order_submitted and not recovery_state_persisted:
                self.cache.delete(signal_lock_key)
            self._publish_activity(
                status="scanning",
                message=f"{request.symbol.upper()} rejected -> {str(exc)}",
                bot_state="WAITING",
                symbol=request.symbol,
                confidence=float(request.confidence),
                intent=f"Re-evaluating {request.symbol.upper()} on future scans",
                readiness=max(0.0, min(100.0, float(request.feature_snapshot.get('strict_trade_score', 0.0) or 0.0))),
                confidence_building=False,
                reason=str(exc),
            )
            raise

    def record_trade_outcome(self, user_id: str, trade_id: str, pnl: float) -> None:
        active_trade = self.redis_state_manager.load_active_trade(trade_id) or {}
        ledger_summary = (
            self.portfolio_ledger.record_trade_close(user_id=user_id, trade_id=trade_id, pnl=pnl)
            if self.portfolio_ledger is not None
            else None
        )
        prior_equity = self.drawdown_protection.load(user_id).current_equity
        current_equity = float((ledger_summary or {}).get("realized_equity", prior_equity + pnl))
        drawdown = self.drawdown_protection.update(user_id, current_equity)
        stability = self._record_model_outcome(active_trade=active_trade, won=pnl > 0)
        rollout_metrics = self.cache.get_json("rollout:metrics") or {"wins": 0, "trades": 0, "gross_profit": 0.0, "gross_loss": 0.0}
        rollout_metrics["trades"] += 1
        rollout_metrics["wins"] += int(pnl > 0)
        rollout_metrics["gross_profit"] += max(0.0, pnl)
        rollout_metrics["gross_loss"] += abs(min(0.0, pnl))
        self.cache.set_json("rollout:metrics", rollout_metrics, ttl=self.settings.monitor_state_ttl_seconds)
        self.rollout_manager.record_performance(
            win_rate=rollout_metrics["wins"] / max(rollout_metrics["trades"], 1),
            profit_factor=rollout_metrics["gross_profit"] / max(rollout_metrics["gross_loss"], 1e-8),
            trades=rollout_metrics["trades"],
            drawdown=drawdown.rolling_drawdown,
        )
        self.performance_tracker.record_signal_outcome(
            signal_type="ai",
            signal_id=trade_id,
            profit=pnl,
            correlation=min(1.0, drawdown.rolling_drawdown + 0.2),
        )
        current_active = max(0, int(self.cache.get("position:active_count") or 0) - 1)
        self.cache.set("position:active_count", str(current_active), ttl=self.settings.monitor_state_ttl_seconds)
        self.system_monitor.set_active_trades(current_active)
        self.redis_state_manager.clear_active_trade(trade_id)
        self.redis_state_manager.unregister_monitored_trade(trade_id)
        if self.meta_controller is not None:
            self.meta_controller.record_trade_outcome(user_id=user_id, active_trade=active_trade, pnl=pnl)
        micro_performance = self.micro_mode_controller.record_trade_outcome(
            user_id,
            account_equity=prior_equity,
            expected_return=float(active_trade.get("expected_return", 0.0)),
            actual_pnl=pnl,
            expected_slippage_bps=float(active_trade.get("expected_slippage_bps", 0.0)),
            actual_slippage_bps=float(active_trade.get("actual_slippage_bps", active_trade.get("expected_slippage_bps", 0.0))),
            latency_ms=float(active_trade.get("execution_latency_ms", 0.0)),
            execution_success=pnl >= -abs(float(active_trade.get("notional", 0.0))) * 0.5,
            live_notional=float(active_trade.get("notional", 0.0)),
        )
        paper_live = self.micro_mode_controller.compare_paper_vs_live(
            expected_paper_pnl=float(active_trade.get("paper_expected_pnl", 0.0)),
            live_pnl=pnl,
            fees=float(active_trade.get("fees", 0.0)),
            slippage_cost=float(active_trade.get("actual_slippage_bps", active_trade.get("expected_slippage_bps", 0.0))) / 10_000,
            latency_ms=float(active_trade.get("execution_latency_ms", 0.0)),
        )
        self.firestore.update_trade(
            trade_id,
            {
                "profit": pnl,
                "realized_pnl": pnl,
                "drawdown_state": drawdown.state,
                "equity_after_trade": current_equity,
                "model_degraded": stability.degraded,
                **micro_performance,
                **paper_live,
            },
        )
        if hasattr(self.firestore, "update_training_sample"):
            self.firestore.update_training_sample(
                trade_id,
                {
                    "outcome": 1.0 if pnl > 0 else 0.0,
                    "realized_pnl": pnl,
                },
            )
        self._safe_firestore_call(
            "save_micro_performance",
            {
                "trade_id": trade_id,
                "user_id": user_id,
                "profit": pnl,
                "realized_pnl": pnl,
                **micro_performance,
                **paper_live,
            },
        )
        if self_healing_report := (
            self.self_healing_service.handle_trade_outcome(trade_id, active_trade, pnl)
            if self.self_healing_service is not None
            else None
        ):
            self.firestore.update_trade(
                trade_id,
                {
                    "self_healing_post_mortem_path": f"post_mortems/{trade_id}.json",
                    "self_healing_top_driver": next(iter(self_healing_report["feature_importance"]), ""),
                    "self_healing_reward_adjustment": self_healing_report["reward_adjustment"],
                },
            )

    def close_trade_position(
        self,
        *,
        user_id: str,
        trade_id: str,
        exit_price: float,
        closed_quantity: float | None = None,
        exit_fee: float = 0.0,
        reason: str = "manual_close",
    ) -> TradeCloseResponse:
        lock_key = self._trade_close_lock_key(trade_id)
        lock_token = str(uuid4())
        if not self.cache.set_if_absent(lock_key, lock_token, ttl=30):
            raise StateError(
                "Trade close already in progress",
                error_code="TRADE_CLOSE_IN_PROGRESS",
            )
        try:
            if self._is_trade_marked_closed(trade_id):
                raise StateError(
                    "Trade is already closed",
                    error_code="TRADE_ALREADY_CLOSED",
                )

            active_trade = self.redis_state_manager.load_active_trade(trade_id)
            if active_trade is None:
                raise ValueError(f"Active trade {trade_id} was not found")
            if str(active_trade.get("status", "")).upper() == "CLOSED":
                raise StateError(
                    "Trade is already closed",
                    error_code="TRADE_ALREADY_CLOSED",
                )
            if self.portfolio_ledger is None:
                raise ValueError("Portfolio ledger is unavailable")

            close_payload = self.portfolio_ledger.close_trade(
                user_id=user_id,
                trade_id=trade_id,
                exit_price=exit_price,
                closed_quantity=closed_quantity,
                exit_fee=exit_fee,
            )
            exit_reason = str(active_trade.get("exit_reason", "") or reason)
            exit_type = str(active_trade.get("exit_type", "") or ("early_exit" if reason != "manual_close" else "manual"))
            drawdown = self.drawdown_protection.update(user_id, close_payload["current_equity"])

            self.performance_tracker.record_signal_outcome(
                signal_type="ai",
                signal_id=trade_id,
                profit=close_payload["realized_pnl"],
                correlation=min(1.0, drawdown.rolling_drawdown + 0.2),
            )
            if close_payload["status"] == "CLOSED":
                stability = self._record_model_outcome(
                    active_trade=active_trade,
                    won=close_payload["realized_pnl"] > 0,
                )
                rollout_metrics = self.cache.get_json("rollout:metrics") or {"wins": 0, "trades": 0, "gross_profit": 0.0, "gross_loss": 0.0}
                rollout_metrics["trades"] += 1
                rollout_metrics["wins"] += int(close_payload["realized_pnl"] > 0)
                rollout_metrics["gross_profit"] += max(0.0, close_payload["realized_pnl"])
                rollout_metrics["gross_loss"] += abs(min(0.0, close_payload["realized_pnl"]))
                self.cache.set_json("rollout:metrics", rollout_metrics, ttl=self.settings.monitor_state_ttl_seconds)
                self.rollout_manager.record_performance(
                    win_rate=rollout_metrics["wins"] / max(rollout_metrics["trades"], 1),
                    profit_factor=rollout_metrics["gross_profit"] / max(rollout_metrics["gross_loss"], 1e-8),
                    trades=rollout_metrics["trades"],
                    drawdown=drawdown.rolling_drawdown,
                )
                current_active = max(0, int(self.cache.get("position:active_count") or 0) - 1)
                self.cache.set("position:active_count", str(current_active), ttl=self.settings.monitor_state_ttl_seconds)
                self.system_monitor.set_active_trades(current_active)
                self.redis_state_manager.unregister_monitored_trade(trade_id)
                if self.meta_controller is not None:
                    self.meta_controller.record_trade_outcome(user_id=user_id, active_trade=active_trade, pnl=close_payload["realized_pnl"])
                micro_performance = self.micro_mode_controller.record_trade_outcome(
                    user_id,
                    account_equity=max(float(close_payload["current_equity"]) - close_payload["realized_pnl"], 0.0),
                    expected_return=float(active_trade.get("expected_return", 0.0)),
                    actual_pnl=close_payload["realized_pnl"],
                    expected_slippage_bps=float(active_trade.get("expected_slippage_bps", 0.0)),
                    actual_slippage_bps=float(active_trade.get("actual_slippage_bps", active_trade.get("expected_slippage_bps", 0.0))),
                    latency_ms=float(active_trade.get("execution_latency_ms", 0.0)),
                    execution_success=close_payload["realized_pnl"] >= -abs(float(active_trade.get("notional", 0.0))) * 0.5,
                    live_notional=float(active_trade.get("notional", 0.0)),
                )
                paper_live = self.micro_mode_controller.compare_paper_vs_live(
                    expected_paper_pnl=float(active_trade.get("paper_expected_pnl", 0.0)),
                    live_pnl=close_payload["realized_pnl"],
                    fees=float(active_trade.get("fees", 0.0)) + exit_fee,
                    slippage_cost=float(active_trade.get("actual_slippage_bps", active_trade.get("expected_slippage_bps", 0.0))) / 10_000,
                    latency_ms=float(active_trade.get("execution_latency_ms", 0.0)),
                )
                self.firestore.save_micro_performance(
                    {
                        "trade_id": trade_id,
                        "user_id": user_id,
                        "profit": close_payload["realized_pnl"],
                        "close_reason": exit_reason,
                        "exit_reason": exit_reason,
                        "exit_type": exit_type,
                        **micro_performance,
                        **paper_live,
                    }
                )
                self.firestore.update_trade(
                    trade_id,
                    {
                        "status": "CLOSED",
                        "exit": exit_price,
                        "exit_fee": exit_fee,
                        "closed_quantity": close_payload["closed_quantity"],
                        "remaining_quantity": close_payload["remaining_quantity"],
                        "profit": close_payload["realized_pnl"],
                        "realized_pnl": close_payload["realized_pnl"],
                        "equity_after_trade": close_payload["current_equity"],
                        "drawdown_state": drawdown.state,
                        "model_degraded": stability.degraded,
                        "close_reason": exit_reason,
                        "exit_reason": exit_reason,
                        "exit_type": exit_type,
                        "max_profit": float(active_trade.get("max_profit", 0.0) or 0.0),
                        **micro_performance,
                        **paper_live,
                    },
                )
                closed_at = datetime.now(timezone.utc)
                self.firestore.publish_trade_to_public_log(
                    {
                        "trade_id": trade_id,
                        "symbol": str(active_trade.get("symbol", "")),
                        "side": str(active_trade.get("side", "")),
                        "entry": float(active_trade.get("entry", 0.0) or 0.0),
                        "exit": exit_price,
                        "executed_quantity": float(active_trade.get("executed_quantity", 0.0) or 0.0),
                        "realized_pnl": close_payload["realized_pnl"],
                        "closed_at": closed_at,
                    }
                )
                self.firestore.update_trade(
                    trade_id,
                    {
                        "closed_at": closed_at,
                    },
                )
                if hasattr(self.firestore, "update_training_sample"):
                    self.firestore.update_training_sample(
                        trade_id,
                        {
                            "outcome": 1.0 if close_payload["realized_pnl"] > 0 else 0.0,
                            "realized_pnl": close_payload["realized_pnl"],
                            "close_reason": exit_reason,
                            "exit_reason": exit_reason,
                            "exit_type": exit_type,
                        },
                    )
                if self.analytics_service is not None:
                    self.analytics_service.record_closed_trade(
                        user_id=user_id,
                        trade_id=trade_id,
                        active_trade=active_trade,
                        close_payload=close_payload,
                        exit_price=exit_price,
                        exit_reason=exit_reason,
                        exit_type=exit_type,
                    )
                if self_healing_report := (
                    self.self_healing_service.handle_trade_outcome(trade_id, active_trade, close_payload["realized_pnl"])
                    if self.self_healing_service is not None
                    else None
                ):
                    self.firestore.update_trade(
                        trade_id,
                        {
                            "self_healing_post_mortem_path": f"post_mortems/{trade_id}.json",
                            "self_healing_top_driver": next(iter(self_healing_report["feature_importance"]), ""),
                            "self_healing_reward_adjustment": self_healing_report["reward_adjustment"],
                        },
                    )
                self._mark_trade_closed(trade_id, close_payload)
            else:
                refreshed_trade = self.redis_state_manager.load_active_trade(trade_id) or {}
                self.update_active_trade_state(trade_id, refreshed_trade) if refreshed_trade else None
                self.firestore.update_trade(
                    trade_id,
                    {
                        "status": "PARTIAL",
                        "exit": exit_price,
                        "exit_fee": exit_fee,
                        "closed_quantity": close_payload["closed_quantity"],
                        "remaining_quantity": close_payload["remaining_quantity"],
                        "close_reason": exit_reason,
                        "exit_reason": exit_reason,
                        "exit_type": exit_type,
                        "max_profit": float(active_trade.get("max_profit", 0.0) or 0.0),
                        "realized_pnl_partial": close_payload["realized_pnl"],
                        "close_reason": reason,
                        "equity_after_trade": close_payload["current_equity"],
                        "drawdown_state": drawdown.state,
                    },
                )
                self.cache.delete(self._trade_closed_key(trade_id))

            return TradeCloseResponse(
                trade_id=trade_id,
                user_id=user_id,
                symbol=str(active_trade.get("symbol", "")),
                side=str(active_trade.get("side", "")),
                status=close_payload["status"],
                closed_quantity=close_payload["closed_quantity"],
                remaining_quantity=close_payload["remaining_quantity"],
                exit_price=close_payload["exit_price"],
                exit_fee=close_payload["exit_fee"],
                realized_pnl=close_payload["realized_pnl"],
                current_equity=close_payload["current_equity"],
                protection_state=drawdown.state,
            )
        finally:
            self.cache.delete_if_value_matches(lock_key, lock_token)

    def _trade_close_lock_key(self, trade_id: str) -> str:
        return f"lock:trade_close:{trade_id}"

    def _trade_closed_key(self, trade_id: str) -> str:
        return f"trade:closed:{trade_id}"

    def _is_trade_marked_closed(self, trade_id: str) -> bool:
        payload = self.cache.get_json(self._trade_closed_key(trade_id)) or {}
        return str(payload.get("status", "")).upper() == "CLOSED"

    def _mark_trade_closed(self, trade_id: str, close_payload: dict) -> None:
        self.cache.set_json(
            self._trade_closed_key(trade_id),
            {
                "status": "CLOSED",
                "closed_quantity": close_payload["closed_quantity"],
                "remaining_quantity": close_payload["remaining_quantity"],
                "realized_pnl": close_payload["realized_pnl"],
                "current_equity": close_payload["current_equity"],
                "closed_at": datetime.now(timezone.utc).isoformat(),
            },
            ttl=self.settings.monitor_state_ttl_seconds,
        )

    def reconcile_startup_state(self) -> list[dict]:
        reconciled: list[dict] = []
        for trade in self.redis_state_manager.restore_active_trades():
            status = trade.get("status")
            order_id = trade.get("order_id")
            symbol = trade.get("symbol")
            if status in {"SUBMITTED", "OPENING"} and order_id and symbol and self.execution_engine is not None:
                try:
                    order_status = self.execution_engine.fetch_order_status(symbol=symbol, order_id=str(order_id))
                except Exception:
                    trade["status"] = "FAILED"
                    self.redis_state_manager.save_active_trade(trade["trade_id"], trade)
                    reconciled.append({"trade_id": trade["trade_id"], "action": "reset"})
                    continue
                exchange_status = order_status.get("status")
                if exchange_status == "FILLED":
                    exit_price = self._reconciliation_exit_price(order_status)
                    exit_fee = self._reconciliation_fee_paid(order_status)
                    executed_qty = float(order_status.get("executedQty", 0.0) or 0.0)
                    owner_user_id = str(trade.get("user_id", "")).strip()
                    if owner_user_id and exit_price > 0:
                        try:
                            close_response = self.close_trade_position(
                                user_id=owner_user_id,
                                trade_id=trade["trade_id"],
                                exit_price=exit_price,
                                closed_quantity=executed_qty if executed_qty > 0 else None,
                                exit_fee=exit_fee,
                                reason="startup_reconciliation",
                            )
                        except StateError as exc:
                            if exc.error_code == "TRADE_ALREADY_CLOSED":
                                reconciled.append({"trade_id": trade["trade_id"], "action": "already_closed"})
                                continue
                            raise
                        reconciled.append(
                            {
                                "trade_id": trade["trade_id"],
                                "action": "close_reconciled",
                                "status": close_response.status,
                                "exit_price": close_response.exit_price,
                            }
                        )
                    else:
                        trade["status"] = "CLOSED"
                        self.redis_state_manager.clear_active_trade(trade["trade_id"])
                        self.firestore.update_trade(trade["trade_id"], {"status": "CLOSED"})
                        reconciled.append({"trade_id": trade["trade_id"], "action": "close_without_pnl"})
                elif exchange_status == "PARTIALLY_FILLED":
                    trade["status"] = "PARTIAL"
                    trade["remaining_qty"] = max(
                        0.0,
                        float(order_status.get("origQty", 0.0)) - float(order_status.get("executedQty", 0.0)),
                    )
                    self.redis_state_manager.save_active_trade(trade["trade_id"], trade)
                    self.firestore.update_trade(
                        trade["trade_id"],
                        {"status": "PARTIAL", "remaining_qty": trade["remaining_qty"]},
                    )
                    reconciled.append({"trade_id": trade["trade_id"], "action": "update_remaining"})
                else:
                    trade["status"] = "FAILED"
                    self.redis_state_manager.save_active_trade(trade["trade_id"], trade)
                    self.firestore.update_trade(trade["trade_id"], {"status": "FAILED"})
                    reconciled.append({"trade_id": trade["trade_id"], "action": "reset"})
            elif status in {"SUBMITTED", "OPENING"}:
                trade["status"] = "FAILED"
                self.redis_state_manager.save_active_trade(trade["trade_id"], trade)
                reconciled.append({"trade_id": trade["trade_id"], "action": "reset"})
        return reconciled

    def _reconciliation_exit_price(self, order_status: dict) -> float:
        raw_price = float(order_status.get("price", 0.0) or 0.0)
        if raw_price > 0:
            return raw_price
        executed_qty = float(order_status.get("executedQty", 0.0) or 0.0)
        cumulative_quote = float(order_status.get("cummulativeQuoteQty", 0.0) or 0.0)
        if executed_qty > 0 and cumulative_quote > 0:
            return cumulative_quote / executed_qty
        return 0.0

    def _reconciliation_fee_paid(self, order_status: dict) -> float:
        return float(order_status.get("feePaid", 0.0) or 0.0)

    def register_signal_subscription(self, user_id: str, tier: str, balance: float, risk_profile: str) -> None:
        self.signal_broadcaster.register_subscription(
            user_id=user_id,
            tier=tier,
            balance=balance,
            risk_profile=risk_profile,
        )

    def dequeue_execution_jobs(self, shard_id: int, limit: int | None = None) -> list[dict]:
        return self.execution_queue_manager.dequeue_batch(shard_id=shard_id, limit=limit)

    async def submit_virtual_order(self, request: TradeRequest) -> dict:
        if request.order_type == "LIMIT" and request.limit_price is None:
            raise ValueError("limit_price is required for LIMIT orders")
        latest_price = await self.market_data.fetch_latest_price(request.symbol)
        quantity = request.quantity or (request.requested_notional or 0.0) / max(latest_price, 1e-8)
        if quantity <= 0:
            raise ValueError("quantity or requested_notional is required")
        if not request.alpha_context.security.tradable:
            raise ValueError("Security scanner blocked trade")
        whale_signal = self._whale_direction(request.alpha_context)
        if self._whale_conflict(request.side, whale_signal):
            raise ValueError("Whale tracker vetoed conflicting trade")
        staged = self.virtual_order_manager.stage_order(
            user_id=request.user_id,
            symbol=request.symbol,
            side=request.side,
            quantity=quantity,
            order_type=request.order_type,
            limit_price=request.limit_price,
            metadata={
                "confidence": request.confidence,
                "reason": request.reason,
                "expected_return": request.expected_return,
                "expected_risk": request.expected_risk,
                "feature_snapshot": request.feature_snapshot,
                "requested_notional": request.requested_notional or latest_price * quantity,
                "signal_id": request.signal_id,
                "alpha_context": request.alpha_context.model_dump(),
                "alpha_decision": request.alpha_decision.model_dump(),
                "strategy": request.strategy,
            },
        )
        return {
            **staged,
            "status": "PENDING_AGGREGATION",
            "symbol": request.symbol,
            "side": request.side,
        }

    async def flush_virtual_orders(self, symbol: str, side: str) -> list[dict]:
        order_book = await self.market_data.fetch_order_book(symbol)
        flushed: list[dict] = []
        for book_key in self.cache.keys(f"vom:book:{symbol}:{side}:*"):
            book = self.virtual_order_manager.load_book(book_key) or {}
            intents = list(book.get("intents", []))
            if not intents:
                continue
            queue_context = {
                "book_key": book_key,
                "aggregate_id": book.get("aggregate_id"),
                "virtual_child_count": len(intents),
            }
            if self.settings.trading_mode == "paper":
                order = await self._submit_order(
                    symbol=symbol,
                    side=side,
                    quantity=float(book.get("total_requested_quantity", 0.0)),
                    order_type=book.get("order_type", "MARKET"),
                    limit_price=book.get("limit_price"),
                    order_book=order_book,
                    queue_context=queue_context,
                )
                result = self.virtual_order_manager.finalize_book(book_key, order)
            else:
                def book_callback(*, symbol: str, side: str, quantity: float, order_type: str, limit_price: float | None, queue_context: dict | None, _book_key=book_key):
                    queue_context = {**(queue_context or {}), "book_key": _book_key}
                    book = self.cache.get_json(_book_key) or {}
                    intents = list(book.get("intents", []))
                    return self.execution_engine.place_virtual_order(
                        symbol=symbol,
                        side=side,
                        intents=intents,
                        order_type=order_type,
                        limit_price=limit_price,
                        order_book=order_book,
                        queue_context=queue_context,
                    )

                result = self.virtual_order_manager.flush_book(book_key, book_callback)
            if result is None:
                continue
            aggregate = result["aggregate"]
            self.firestore.save_performance_snapshot(
                f"vom:{aggregate['aggregate_id']}",
                {
                    **aggregate,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            for allocation in result["allocations"]:
                self._record_virtual_allocation(allocation, aggregate, order_book)
            flushed.append(result)
        return flushed

    async def _claim_signal(self, signal_id: str, symbol: str, side: str) -> dict | None:
        cached_response = self._load_cached_signal_response(signal_id)
        if cached_response is not None:
            return cached_response
        active_response = self._load_signal_response_from_active_trade(signal_id, symbol, side)
        if active_response is not None:
            self._store_signal_response(signal_id, TradeResponse(**active_response))
            active_response["duplicate_signal"] = True
            return active_response
        existing_response = self._load_signal_response_from_trade(signal_id, symbol, side)
        if existing_response is not None:
            self._store_signal_response(signal_id, TradeResponse(**existing_response))
            existing_response["duplicate_signal"] = True
            return existing_response
        claimed = self.cache.set_if_absent(
            f"signal:lock:{signal_id}",
            "1",
            ttl=self.settings.signal_dedup_ttl_seconds,
        )
        if claimed:
            return None
        for _ in range(5):
            await asyncio.sleep(0.1)
            cached_response = self._load_cached_signal_response(signal_id)
            if cached_response is not None:
                return cached_response
            active_response = self._load_signal_response_from_active_trade(signal_id, symbol, side)
            if active_response is not None:
                self._store_signal_response(signal_id, TradeResponse(**active_response))
                active_response["duplicate_signal"] = True
                return active_response
            existing_response = self._load_signal_response_from_trade(signal_id, symbol, side)
            if existing_response is not None:
                self._store_signal_response(signal_id, TradeResponse(**existing_response))
                existing_response["duplicate_signal"] = True
                return existing_response
        return {
            "trade_id": f"duplicate-{signal_id}",
            "status": "IGNORED",
            "trading_mode": self.settings.trading_mode,
            "symbol": symbol,
            "side": side,
            "executed_price": 0.0,
            "executed_quantity": 0.0,
            "stop_loss": 0.0,
            "trailing_stop_pct": 0.0,
            "take_profit": 0.0,
            "fee_paid": 0.0,
            "slippage_bps": 0.0,
            "filled_ratio": 0.0,
            "duplicate_signal": True,
            "rollout_capital_fraction": self.rollout_manager.status().capital_fraction,
            "explanation": "Duplicate signal ignored while original execution is still in progress",
            "alpha_score": 0.0,
            "macro_bias_multiplier": 1.0,
            "macro_bias_regime": "NEUTRAL",
        }

    def _load_cached_signal_response(self, signal_id: str) -> dict | None:
        cached = self.cache.get(f"signal:response:{signal_id}")
        if not cached:
            return None
        payload = json.loads(cached)
        payload["duplicate_signal"] = True
        return payload

    def _store_signal_response(self, signal_id: str, response: TradeResponse) -> None:
        self.cache.set(
            f"signal:response:{signal_id}",
            json.dumps(response.model_dump(mode="json")),
            ttl=self.settings.signal_dedup_ttl_seconds,
        )

    def _persist_opening_recovery_state(
        self,
        *,
        request: TradeRequest,
        response: TradeResponse,
        route: dict,
        quantity: float,
        requested_notional: float,
    ) -> None:
        payload = {
            "trade_id": response.trade_id,
            "order_id": response.trade_id,
            "signal_id": request.signal_id,
            "user_id": request.user_id,
            "symbol": request.symbol,
            "side": request.side,
            "status": "OPENING",
            "submitted_state": "OPENING",
            "requested_quantity": quantity,
            "executed_quantity": quantity,
            "requested_notional": requested_notional,
            "order_type": request.order_type,
            "chain": route.get("chain"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.redis_state_manager.save_active_trade(response.trade_id, payload)
        self.redis_state_manager.remember_order(
            response.trade_id,
            {
                "symbol": request.symbol,
                "trade_id": response.trade_id,
                "status": "OPENING",
                "chain": route["chain"],
                "signal_id": request.signal_id,
            },
        )
        if request.signal_id:
            self.redis_state_manager.remember_signal_trade(request.signal_id, response.trade_id)

    def _persist_active_trade_details(
        self,
        *,
        request: TradeRequest,
        response: TradeResponse,
        route: dict,
        meta_decision,
        spread_bps: float,
        executed_notional: float,
        execution_priority: int,
        scheduled_delay_ms: float,
        shard_id: int,
        execution_latency_ms: float,
    ) -> None:
        existing = self.redis_state_manager.load_active_trade(response.trade_id) or {}
        payload = {
            **existing,
            "trade_id": response.trade_id,
            "user_id": request.user_id,
            "symbol": request.symbol,
            "side": request.side,
            "entry": response.executed_price,
            "executed_quantity": response.executed_quantity,
            "stop_loss": response.stop_loss,
            "initial_stop_loss": float(existing.get("initial_stop_loss", response.stop_loss) or response.stop_loss),
            "trailing_stop_pct": response.trailing_stop_pct,
            "take_profit": response.take_profit,
            "status": "OPENING",
            "order_id": response.trade_id,
            "submitted_state": "OPENING",
            "signal_id": request.signal_id,
            "expected_return": request.expected_return or 0.0,
            "expected_slippage_bps": spread_bps,
            "execution_latency_ms": execution_latency_ms,
            "notional": executed_notional,
            "paper_expected_pnl": (request.expected_return or 0.0) * executed_notional,
            "actual_slippage_bps": response.slippage_bps,
            "fees": response.fee_paid,
            "feature_snapshot": request.feature_snapshot,
            "regime": str(request.feature_snapshot.get("regime", request.feature_snapshot.get("regime_type", "RANGING"))).upper(),
            "probability_features": self._extract_probability_features(request.feature_snapshot),
            "confidence": request.confidence,
            "entry_reason": request.reason,
            "exit_reason": str(existing.get("exit_reason", "") or ""),
            "max_profit": float(existing.get("max_profit", 0.0) or 0.0),
            "exit_type": str(existing.get("exit_type", "") or ""),
            "risk_fraction": float(request.feature_snapshot.get("portfolio_risk_fraction", existing.get("risk_fraction", 0.0)) or 0.0),
            "portfolio_correlation_risk": float(
                request.feature_snapshot.get(
                    "portfolio_correlation_risk",
                    existing.get("portfolio_correlation_risk", 0.0),
                )
                or 0.0
            ),
            "trade_success_probability": float(
                request.feature_snapshot.get("trade_success_probability", request.confidence)
            ),
            "raw_trade_success_probability": float(
                request.feature_snapshot.get(
                    "raw_trade_success_probability",
                    request.feature_snapshot.get("trade_success_probability", request.confidence),
                )
            ),
            "probability_model_version": str(
                request.feature_snapshot.get(
                    "probability_model_version",
                    request.feature_snapshot.get("model_version", "unknown"),
                )
            ),
            "expected_risk": request.expected_risk or 0.0,
            "regime_confidence": float(request.feature_snapshot.get("regime_confidence", 0.5)),
            "strategy": request.strategy,
            "meta_strategy": meta_decision.selected_strategy if meta_decision is not None else request.strategy,
            "macro_bias_multiplier": response.macro_bias_multiplier,
            "macro_bias_regime": response.macro_bias_regime,
            "execution_shard": shard_id,
            "execution_priority": execution_priority,
            "scheduled_delay_ms": scheduled_delay_ms,
            "exchange_status": response.status,
        }
        self.update_active_trade_state(response.trade_id, payload)
        self.redis_state_manager.remember_order(
            response.trade_id,
            {
                "symbol": request.symbol,
                "trade_id": response.trade_id,
                "status": response.status,
                "chain": route["chain"],
                "signal_id": request.signal_id,
            },
        )

    def _load_signal_response_from_active_trade(self, signal_id: str, symbol: str, side: str) -> dict | None:
        trade_id = self.redis_state_manager.load_signal_trade(signal_id)
        if not trade_id:
            return None
        active_trade = self.redis_state_manager.load_active_trade(trade_id)
        if active_trade is None:
            return None
        return {
            "trade_id": trade_id,
            "status": str(active_trade.get("status", "OPENING")),
            "trading_mode": self.settings.trading_mode,
            "symbol": str(active_trade.get("symbol", symbol)),
            "side": str(active_trade.get("side", side)),
            "executed_price": float(active_trade.get("entry", 0.0) or 0.0),
            "executed_quantity": float(active_trade.get("executed_quantity", active_trade.get("requested_quantity", 0.0)) or 0.0),
            "stop_loss": float(active_trade.get("stop_loss", 0.0) or 0.0),
            "trailing_stop_pct": float(active_trade.get("trailing_stop_pct", 0.0) or 0.0),
            "take_profit": float(active_trade.get("take_profit", 0.0) or 0.0),
            "fee_paid": float(active_trade.get("fees", 0.0) or 0.0),
            "slippage_bps": float(active_trade.get("actual_slippage_bps", 0.0) or 0.0),
            "filled_ratio": 1.0 if float(active_trade.get("executed_quantity", 0.0) or 0.0) > 0 else 0.0,
            "duplicate_signal": False,
            "rollout_capital_fraction": self.rollout_manager.status().capital_fraction,
            "explanation": "Recovered in-progress trade from opening state",
            "alpha_score": float(active_trade.get("alpha_score", 0.0) or 0.0),
            "macro_bias_multiplier": float(active_trade.get("macro_bias_multiplier", 1.0) or 1.0),
            "macro_bias_regime": str(active_trade.get("macro_bias_regime", "NEUTRAL")),
        }

    def _load_signal_response_from_trade(self, signal_id: str, symbol: str, side: str) -> dict | None:
        trade_record = self.firestore.load_trade_by_signal_id(signal_id)
        if trade_record is None:
            return None
        trade_id = str(trade_record.get("trade_id", "") or "")
        active_trade = self.redis_state_manager.load_active_trade(trade_id) if trade_id else None
        alpha_decision = trade_record.get("alpha_decision") or {}
        payload = {
            "trade_id": trade_id or f"trade-for-{signal_id}",
            "status": str(trade_record.get("status", active_trade.get("status") if active_trade else "UNKNOWN")),
            "trading_mode": str(trade_record.get("trading_mode", self.settings.trading_mode)),
            "symbol": str(trade_record.get("symbol", active_trade.get("symbol") if active_trade else symbol)),
            "side": str(trade_record.get("side", active_trade.get("side") if active_trade else side)),
            "executed_price": float(trade_record.get("entry", active_trade.get("entry") if active_trade else 0.0) or 0.0),
            "executed_quantity": float(
                trade_record.get("executed_quantity", active_trade.get("executed_quantity") if active_trade else 0.0) or 0.0
            ),
            "stop_loss": float(trade_record.get("stop_loss", active_trade.get("stop_loss") if active_trade else 0.0) or 0.0),
            "trailing_stop_pct": float(
                trade_record.get("trailing_stop_pct", active_trade.get("trailing_stop_pct") if active_trade else 0.0) or 0.0
            ),
            "take_profit": float(trade_record.get("take_profit", active_trade.get("take_profit") if active_trade else 0.0) or 0.0),
            "fee_paid": float(trade_record.get("fee_paid", active_trade.get("fees") if active_trade else 0.0) or 0.0),
            "slippage_bps": float(trade_record.get("slippage_bps", active_trade.get("actual_slippage_bps") if active_trade else 0.0) or 0.0),
            "filled_ratio": float(trade_record.get("filled_ratio", 1.0) or 0.0),
            "duplicate_signal": False,
            "rollout_capital_fraction": float(trade_record.get("rollout_capital_fraction", 1.0) or 1.0),
            "explanation": str(trade_record.get("explanation", "Recovered duplicate signal response")),
            "alpha_score": float(trade_record.get("alpha_score", alpha_decision.get("final_score", 0.0)) or 0.0),
            "macro_bias_multiplier": float(
                trade_record.get("macro_bias_multiplier", active_trade.get("macro_bias_multiplier") if active_trade else 1.0) or 1.0
            ),
            "macro_bias_regime": str(
                trade_record.get("macro_bias_regime", active_trade.get("macro_bias_regime") if active_trade else "NEUTRAL")
            ),
        }
        return payload

    async def _submit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str,
        limit_price: float | None,
        order_book: dict | None,
        queue_context: dict | None,
    ) -> dict:
        if self.settings.trading_mode == "paper":
            return await self.paper_execution_engine.place_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                limit_price=limit_price,
                order_book=order_book,
            )
        return self.execution_engine.place_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
            order_book=order_book,
            queue_context=queue_context,
        )

    def _record_virtual_allocation(self, allocation: dict, aggregate: dict, order_book: dict | None) -> None:
        trade_id = f"{aggregate['exchange_order_id']}:{allocation['intent_id']}"
        alpha_context = allocation.get("alpha_context", {})
        alpha_decision = allocation.get("alpha_decision", {})
        feature_snapshot = allocation.get("feature_snapshot", {})
        tax_estimate = self.tax_engine.estimate_trade_tax(
            profit=float(allocation.get("expected_return") or 0.0) * float(allocation.get("requested_notional") or 0.0)
        )
        self.firestore.save_trade(
            {
                "trade_id": trade_id,
                "user_id": allocation["user_id"],
                "symbol": allocation["symbol"],
                "side": allocation["side"],
                "entry": allocation["executed_price"],
                "executed_quantity": allocation["allocated_quantity"],
                "executed_notional": float(allocation["allocated_quantity"]) * float(allocation["executed_price"]),
                "exit": None,
                "profit": None,
                "ai_confidence": allocation.get("confidence"),
                "reason": allocation.get("reason"),
                "status": allocation["allocation_status"],
                "trading_mode": self.settings.trading_mode,
                "fee_paid": allocation["fee_paid"],
                "slippage_bps": self._spread_bps(order_book or {"bids": [], "asks": []}),
                "filled_ratio": allocation["fill_ratio"],
                "expected_return": allocation.get("expected_return"),
                "expected_risk": allocation.get("expected_risk"),
                "features": feature_snapshot,
                "signal_id": allocation.get("signal_id"),
                "alpha": alpha_context,
                "alpha_decision": alpha_decision,
                "aggregate_order_id": aggregate["exchange_order_id"],
                "virtual_order_id": aggregate["aggregate_id"],
                "requested_quantity": allocation["requested_quantity"],
                "allocated_quantity": allocation["allocated_quantity"],
                "remaining_quantity": allocation["remaining_quantity"],
                "execution_mode": "virtual_aggregated",
                **tax_estimate,
            }
        )
        self.firestore.save_training_sample(
            {
                "sample_id": trade_id,
                "trade_id": trade_id,
                "user_id": allocation["user_id"],
                "symbol": allocation["symbol"],
                "features": feature_snapshot,
                "probability_features": self._extract_probability_features(feature_snapshot),
                "expected_return": allocation.get("expected_return"),
                "expected_risk": allocation.get("expected_risk"),
                "confidence": allocation.get("confidence"),
                "trading_mode": self.settings.trading_mode,
                "outcome": None,
                "alpha": alpha_context,
                "alpha_decision": alpha_decision,
                "aggregate_order_id": aggregate["exchange_order_id"],
                "virtual_order_id": aggregate["aggregate_id"],
            }
        )
        self.firestore.save_tax_record(
            {
                "trade_id": trade_id,
                "user_id": allocation["user_id"],
                "symbol": allocation["symbol"],
                "aggregate_order_id": aggregate["exchange_order_id"],
                **tax_estimate,
            }
        )
        self.redis_state_manager.save_active_trade(
            trade_id,
            {
                "trade_id": trade_id,
                "symbol": allocation["symbol"],
                "side": allocation["side"],
                "entry": allocation["executed_price"],
                "user_id": allocation["user_id"],
                "executed_quantity": allocation["allocated_quantity"],
                "status": allocation["allocation_status"],
                "order_id": aggregate["exchange_order_id"],
                "submitted_state": "SUBMITTED",
                "expected_return": allocation.get("expected_return") or 0.0,
                "expected_slippage_bps": self._spread_bps(order_book or {"bids": [], "asks": []}),
                "execution_latency_ms": 0.0,
                "notional": float(allocation["allocated_quantity"]) * float(allocation["executed_price"]),
                "fees": allocation["fee_paid"],
                "aggregate_order_id": aggregate["exchange_order_id"],
                "virtual_order_id": aggregate["aggregate_id"],
            },
        )
        if self.portfolio_ledger is not None:
            self.portfolio_ledger.record_trade_open(
                user_id=allocation["user_id"],
                trade_id=trade_id,
                symbol=allocation["symbol"],
                side=allocation["side"],
                entry_price=float(allocation["executed_price"]),
                executed_quantity=float(allocation["allocated_quantity"]),
                notional=float(allocation["allocated_quantity"]) * float(allocation["executed_price"]),
                fee_paid=float(allocation["fee_paid"]),
            )

    def _build_alpha_context(
        self,
        snapshot,
        whale_data: dict,
        liquidity_data: dict,
        sentiment_data: dict,
        security_data: dict,
        execution_route: dict,
        tax_data: dict,
        inference_reason: str,
    ) -> AlphaContext:
        explainability = ExplainabilityContext(
            indicators={
                "volatility": snapshot.volatility,
                "atr": snapshot.atr,
                "order_book_imbalance": snapshot.order_book_imbalance,
            },
            whale_summary=whale_data["summary"],
            sentiment_summary=f"Narrative={sentiment_data['narrative']} hype={sentiment_data['hype_score']:.2f}",
            risk_summary=f"Liquidity risk={liquidity_data['rug_pull_risk']:.2f} security tradable={security_data['tradable']}",
            execution_summary=f"Chain={execution_route['chain']} relay={execution_route['relay_strategy']}",
            human_reason=(
                f"Trade combines {inference_reason}; whale score {whale_data['score']:.2f}; "
                f"sentiment narrative {sentiment_data['narrative']}; liquidity stability {liquidity_data['liquidity_stability']:.2f}"
            ),
        )
        return AlphaContext(
            whale=WhaleContext(**{key: whale_data[key] for key in WhaleContext.model_fields if key in whale_data}),
            liquidity=LiquidityContext(**{key: liquidity_data[key] for key in LiquidityContext.model_fields if key in liquidity_data}),
            sentiment=SentimentContext(**{key: sentiment_data[key] for key in SentimentContext.model_fields if key in sentiment_data}),
            security=SecurityContext(**{key: security_data[key] for key in SecurityContext.model_fields if key in security_data}),
            tax=TaxContext(**tax_data),
            explainability=explainability,
        )

    def _alpha_risk_score(self, alpha: AlphaContext) -> float:
        return min(
            1.0,
            alpha.liquidity.rug_pull_risk * 0.35
            + alpha.security.honeypot_risk * 0.30
            + alpha.security.ownership_risk * 0.15
            + alpha.sentiment.hype_score * 0.10
            + alpha.whale.unusual_activity_score * 0.10,
        )

    def _record_model_outcome(self, *, active_trade: dict, won: bool):
        try:
            return self.model_stability.record_live_outcome(
                won=won,
                predicted_probability=float(
                    active_trade.get("trade_success_probability", active_trade.get("confidence", 0.0))
                ),
                feature_snapshot=active_trade.get("probability_features") or active_trade.get("feature_snapshot"),
                model_version=str(
                    active_trade.get("probability_model_version", active_trade.get("model_version", "")) or ""
                ),
            )
        except TypeError:
            return self.model_stability.record_live_outcome(won=won)

    async def _portfolio_correlation(self, *, user_id: str, symbol: str, features: dict[str, float] | None) -> float:
        features = features or {}
        if self.portfolio_ledger is None:
            return self._heuristic_correlation(symbol, features)
        portfolio_summary = self.portfolio_ledger.portfolio_risk_summary(user_id)
        symbol_exposures = portfolio_summary.get("symbol_exposures") or {}
        candidate_symbol = symbol.upper()
        if not symbol_exposures:
            return self._heuristic_correlation(candidate_symbol, features)
        if candidate_symbol in symbol_exposures:
            return 1.0

        active_symbols = [portfolio_symbol for portfolio_symbol in symbol_exposures if portfolio_symbol and portfolio_symbol != candidate_symbol]
        if not active_symbols:
            return self._heuristic_correlation(candidate_symbol, features)

        intervals = ("15m",)
        try:
            coroutines = [
                self.market_data.fetch_multi_timeframe_ohlcv(candidate_symbol, intervals=intervals),
                *[
                    self.market_data.fetch_multi_timeframe_ohlcv(portfolio_symbol, intervals=intervals)
                    for portfolio_symbol in active_symbols
                ],
            ]
            results = await asyncio.gather(*coroutines, return_exceptions=True)
        except Exception:
            return self._heuristic_correlation(candidate_symbol, features)

        candidate_frames = results[0] if results else None
        portfolio_frames = results[1:] if len(results) > 1 else []
        if isinstance(candidate_frames, Exception):
            return self._heuristic_correlation(candidate_symbol, features)

        candidate_returns = self._close_returns(candidate_frames)
        if not candidate_returns:
            return self._heuristic_correlation(candidate_symbol, features)

        total_exposure = sum(float(exposure) for exposure in symbol_exposures.values()) or 1.0
        weighted_correlation = 0.0
        applied_weight = 0.0
        for portfolio_symbol, frame_payload in zip(active_symbols, portfolio_frames, strict=False):
            if isinstance(frame_payload, Exception):
                continue
            peer_returns = self._close_returns(frame_payload)
            correlation = self._series_correlation(candidate_returns, peer_returns)
            if correlation is None:
                continue
            weight = float(symbol_exposures.get(portfolio_symbol, 0.0)) / total_exposure
            weighted_correlation += correlation * weight
            applied_weight += weight

        if applied_weight <= 0:
            return self._heuristic_correlation(candidate_symbol, features)
        return max(0.0, min(1.0, weighted_correlation / applied_weight))

    def _heuristic_correlation(self, symbol: str, features: dict[str, float]) -> float:
        symbol_factor = (abs(hash(symbol)) % 25) / 100
        return min(0.95, 0.45 + symbol_factor + abs(features.get("15m_return", 0.0)) * 2)

    def _close_returns(self, frames: dict[str, object] | None) -> list[float]:
        if not frames:
            return []
        frame = frames.get("15m")
        if frame is None or "close" not in frame:
            return []
        closes = frame["close"].astype(float)
        returns = closes.pct_change().dropna().tail(self.settings.portfolio_correlation_lookback_candles)
        return [float(value) for value in returns.tolist() if math.isfinite(float(value))]

    def _series_correlation(self, left: list[float], right: list[float]) -> float | None:
        overlap = min(len(left), len(right), self.settings.portfolio_correlation_lookback_candles)
        if overlap < self.settings.portfolio_correlation_min_overlap:
            return None
        x = left[-overlap:]
        y = right[-overlap:]
        mean_x = sum(x) / overlap
        mean_y = sum(y) / overlap
        covariance = sum((lhs - mean_x) * (rhs - mean_y) for lhs, rhs in zip(x, y, strict=False))
        variance_x = sum((lhs - mean_x) ** 2 for lhs in x)
        variance_y = sum((rhs - mean_y) ** 2 for rhs in y)
        if variance_x <= 0 or variance_y <= 0:
            return None
        correlation = covariance / math.sqrt(variance_x * variance_y)
        if not math.isfinite(correlation):
            return None
        return max(0.0, min(1.0, abs(correlation)))

    def _theme_for_symbol(self, symbol: str) -> str:
        if self.portfolio_ledger is not None:
            return self.portfolio_ledger.theme_for_symbol(symbol)
        return "OTHER"

    def _hours_since_rebalance(self) -> int:
        return int(self.cache.get("portfolio:hours_since_rebalance") or self.settings.rebalance_interval_hours)

    def _human_explanation(self, request: TradeRequest, route: dict, macro_bias: dict | None = None) -> str:
        macro_bias = macro_bias or self._macro_bias_payload(request)
        return (
            f"{request.side} executed because AI expected return was {request.expected_return or 0.0:.4f}, "
            f"whale summary was '{request.alpha_context.whale.summary}', narrative was "
            f"'{request.alpha_context.sentiment.narrative}', liquidity risk was "
            f"{request.alpha_context.liquidity.rug_pull_risk:.2f}, and route selected {route['chain']} "
            f"with {'private relay' if route['private_relay'] else 'standard broadcast'}. "
            f"Macro bias={macro_bias['regime']} x{macro_bias['multiplier']:.2f}."
        )

    def _macro_bias_payload(self, request: TradeRequest) -> dict:
        cached = self.cache.get_json("macro:global_bias") or {}
        multiplier = float(request.macro_bias_multiplier if request.macro_bias_multiplier is not None else cached.get("multiplier", 1.0))
        regime = str(request.macro_bias_regime or cached.get("regime", "NEUTRAL")).upper()
        reason = str(cached.get("reason", "Macro worker unavailable"))
        if regime == "BEARISH":
            multiplier = min(multiplier, 0.50)
        return {
            "multiplier": max(0.1, multiplier),
            "regime": regime,
            "reason": reason,
        }

    def _macro_adjusted_exit_levels(
        self,
        *,
        side: str,
        executed_price: float,
        expected_return: float,
        macro_bias: dict,
        feature_snapshot: dict[str, float] | None = None,
    ) -> tuple[float, float, float]:
        feature_snapshot = feature_snapshot or {}
        atr = float(feature_snapshot.get("atr", feature_snapshot.get("15m_atr", feature_snapshot.get("5m_atr", 0.0))) or 0.0)
        adaptive = self._adaptive_strategy_config()
        stop_loss_multiplier = float(adaptive.get("stop_loss_multiplier", 1.0) or 1.0)
        if atr > 0:
            if side == "BUY":
                stop_loss = min(executed_price - (2.0 * atr * stop_loss_multiplier), executed_price * 0.99)
            else:
                stop_loss = max(executed_price + (2.0 * atr * stop_loss_multiplier), executed_price * 1.01)
            trailing_stop_pct = max(0.0025, min(0.05, (2.5 * atr * stop_loss_multiplier) / max(executed_price, 1e-8)))
        else:
            trailing_stop_pct = 0.004
            stop_loss = executed_price * (0.994 if side == "BUY" else 1.006)
        take_profit = 0.0
        if macro_bias["regime"] == "BEARISH":
            if side == "BUY":
                trailing_stop_pct = 0.0025
                stop_loss = max(stop_loss, executed_price * (1 - trailing_stop_pct))
            else:
                trailing_stop_pct = max(0.0025, trailing_stop_pct * 0.85)
        return round(stop_loss, 8), round(trailing_stop_pct, 6), round(take_profit, 8)

    def _whale_direction(self, alpha: AlphaContext) -> str:
        if alpha.whale.accumulation_score >= 0.65 and alpha.whale.unusual_activity_score < 0.80:
            return "BUY"
        if alpha.whale.unusual_activity_score >= 0.80 and alpha.liquidity.rug_pull_risk >= 0.45:
            return "SELL"
        return "HOLD"

    def _whale_conflict(self, ai_decision: str, whale_signal: str) -> bool:
        return (ai_decision == "BUY" and whale_signal == "SELL") or (ai_decision == "SELL" and whale_signal == "BUY")

    def _decision_reason(self, ai_decision: str, whale_signal: str, whale_conflict_flag: bool, alpha_decision: dict) -> str:
        if whale_conflict_flag:
            return f"Blocked: AI={ai_decision} conflicts with whale signal={whale_signal}"
        if not alpha_decision["allow_trade"]:
            return "Blocked: alpha engine rejected return/risk profile"
        return f"Approved: alpha final score {alpha_decision['final_score']:.2f}"

    def _strict_trade_gate(
        self,
        *,
        features: dict[str, float],
        side: str,
        confidence: float,
        regime: str,
        volatility: float,
        confidence_floor_override: float | None = None,
    ) -> dict[str, object]:
        normalized_side = str(side or "HOLD").upper()
        if normalized_side not in {"BUY", "SELL"}:
            return {
                "score": 0.0,
                "allow_trade": False,
                "reason": "No directional setup",
                "reason_code": "no_direction",
                "components": {},
            }
        confidence_ok = float(confidence) >= float(
            confidence_floor_override
            if confidence_floor_override is not None
            else self.settings.strict_trade_confidence_floor
        )
        if not features:
            return {
                "score": round(float(confidence) * 100, 6),
                "allow_trade": bool(confidence_ok),
                "reason": "Indicator snapshot unavailable; using confidence floor only" if confidence_ok else "Confidence below strict floor",
                "reason_code": "confidence_only" if confidence_ok else "confidence_below_floor",
                "components": {"confidence_floor_passed": 1.0 if confidence_ok else 0.0},
            }
        indicator_keys = {
            "15m_structure_bullish",
            "15m_structure_bearish",
            "5m_structure_bullish",
            "5m_structure_bearish",
            "15m_mfi",
            "5m_mfi",
            "15m_volume_avg_20",
            "5m_volume_avg_20",
        }
        if not any(key in features for key in indicator_keys):
            return {
                "score": round(float(confidence) * 100, 6),
                "allow_trade": bool(confidence_ok),
                "reason": "Strict indicators missing; using confidence floor only" if confidence_ok else "Confidence below strict floor",
                "reason_code": "confidence_only" if confidence_ok else "confidence_below_floor",
                "components": {"confidence_floor_passed": 1.0 if confidence_ok else 0.0},
            }
        bullish_structure = bool(float(features.get("15m_structure_bullish", features.get("5m_structure_bullish", 0.0)) or 0.0) >= 1.0)
        bearish_structure = bool(float(features.get("15m_structure_bearish", features.get("5m_structure_bearish", 0.0)) or 0.0) >= 1.0)
        structure_ok = bullish_structure if normalized_side == "BUY" else bearish_structure
        adaptive = self._adaptive_strategy_config()
        structure_weight = float(adaptive.get("confluence_weight_structure", self.settings.confluence_weight_structure))
        momentum_weight = float(adaptive.get("confluence_weight_momentum", self.settings.confluence_weight_momentum))
        volume_weight = float(adaptive.get("confluence_weight_volume", self.settings.confluence_weight_volume))
        total_weight = max(structure_weight + momentum_weight + volume_weight, 1e-8)

        volume = float(features.get("15m_volume", features.get("5m_volume", 0.0)) or 0.0)
        volume_avg = float(features.get("15m_volume_avg_20", features.get("5m_volume_avg_20", volume)) or volume)
        volume_ratio = volume / max(volume_avg, 1e-8)
        volume_ok = volume_ratio >= float(self.settings.strict_trade_volume_spike_threshold)

        mfi = float(features.get("15m_mfi", features.get("5m_mfi", 50.0)) or 50.0)
        momentum_ok = 50.0 < mfi < 80.0 if normalized_side == "BUY" else 20.0 < mfi < 50.0

        adx = float(features.get("15m_adx", features.get("5m_adx", 0.0)) or 0.0)
        trend_regime_ok = str(regime or "RANGING").upper() == "TRENDING" and adx >= float(self.settings.strict_trade_structure_adx_floor)

        volatility_ok = float(volatility) > 0.0 and float(volatility) <= float(self.settings.trade_safety_max_volatility)

        score = 0.0
        score += 70.0 * (structure_weight / total_weight) if structure_ok else 0.0
        score += 70.0 * (volume_weight / total_weight) if volume_ok else 0.0
        score += 70.0 * (momentum_weight / total_weight) if momentum_ok else 0.0
        score += 20.0 if trend_regime_ok else 0.0
        score += 10.0 if volatility_ok else 0.0

        components = {
            "market_structure": round(70.0 * (structure_weight / total_weight), 6) if structure_ok else 0.0,
            "volume_spike": round(70.0 * (volume_weight / total_weight), 6) if volume_ok else 0.0,
            "mfi_momentum": round(70.0 * (momentum_weight / total_weight), 6) if momentum_ok else 0.0,
            "trend_regime": 20.0 if trend_regime_ok else 0.0,
            "acceptable_volatility": 10.0 if volatility_ok else 0.0,
            "confidence_floor_passed": 1.0 if confidence_ok else 0.0,
            "volume_ratio": round(volume_ratio, 6),
            "mfi": round(mfi, 6),
            "adx": round(adx, 6),
            "adaptive_weight_structure": round(structure_weight, 6),
            "adaptive_weight_momentum": round(momentum_weight, 6),
            "adaptive_weight_volume": round(volume_weight, 6),
        }

        reason_parts: list[str] = []
        if structure_ok:
            reason_parts.append("structure aligned")
        if volume_ok:
            reason_parts.append("volume spike")
        if momentum_ok:
            reason_parts.append("MFI momentum")
        if trend_regime_ok:
            reason_parts.append("clean trend regime")
        if volatility_ok:
            reason_parts.append("volatility acceptable")

        if not confidence_ok:
            reason_code = "confidence_below_floor"
            reason = "Confidence below strict floor"
        elif score < float(self.settings.strict_trade_score_threshold):
            reason_code = "score_below_threshold"
            reason = f"Score {score:.1f} below threshold"
        else:
            reason_code = "passed"
            reason = " + ".join(reason_parts) or "strict gate passed"
        return {
            "score": round(score, 6),
            "allow_trade": bool(confidence_ok and score >= float(self.settings.strict_trade_score_threshold)),
            "reason": reason,
            "reason_code": reason_code,
            "components": components,
        }

    def _adaptive_strategy_config(self) -> dict:
        if self.strategy_controller is not None:
            return self.strategy_controller.current_config("system")
        cached = self.cache.get_json("strategy:adaptive_config:system")
        if cached:
            return cached
        return {
            "confluence_weight_structure": float(self.settings.confluence_weight_structure),
            "confluence_weight_momentum": float(self.settings.confluence_weight_momentum),
            "confluence_weight_volume": float(self.settings.confluence_weight_volume),
            "trailing_aggressiveness": float(self.settings.trailing_aggressiveness),
            "symbol_priorities": {},
        }

    def _symbol_priority_multiplier(self, symbol: str) -> float:
        normalized = str(symbol or "").upper().strip()
        adaptive = self._adaptive_strategy_config()
        return float(adaptive.get("symbol_priorities", {}).get(normalized, 1.0) or 1.0)

    def _symbol_allocation_multiplier(self, symbol: str) -> float:
        normalized = str(symbol or "").upper().strip()
        adaptive = self._adaptive_strategy_config()
        return float(adaptive.get("symbol_allocations", {}).get(normalized, 1.0) or 1.0)

    def _final_signal_action(self, snapshot, inference, strategy_decision) -> str:
        if strategy_decision.signal in {"BUY", "SELL"}:
            return strategy_decision.signal
        if inference.decision in {"BUY", "SELL"}:
            return inference.decision
        return "BUY" if snapshot.order_book_imbalance >= 0 else "SELL"

    def _store_signal_diagnostics(self, symbol: str, diagnostics: dict) -> None:
        self.cache.set_json(
            f"signal:diagnostics:{symbol.upper()}",
            diagnostics,
            ttl=self.settings.signal_version_ttl_seconds,
        )

    def _market_data_diagnostics(self, frames: dict[str, object]) -> dict:
        diagnostics: dict[str, object] = {"frames": {}, "stale": False, "empty_intervals": []}
        now = datetime.now(timezone.utc)
        for interval, frame in frames.items():
            if frame is None or getattr(frame, "empty", True):
                diagnostics["empty_intervals"].append(interval)
                continue
            last_close_ms = float(frame["close_time"].iloc[-1]) if "close_time" in frame else 0.0
            last_close_at = datetime.fromtimestamp(last_close_ms / 1000, tz=timezone.utc) if last_close_ms else now
            age_seconds = max(0.0, (now - last_close_at).total_seconds())
            diagnostics["frames"][interval] = {
                "rows": int(len(frame)),
                "last_close_at": last_close_at.isoformat(),
                "age_seconds": round(age_seconds, 3),
            }
            if age_seconds > {"1m": 180, "5m": 900, "15m": 2700, "1h": 7200}.get(interval, 900):
                diagnostics["stale"] = True
        return diagnostics

    def _safe_firestore_call(self, method_name: str, *args, swallow_exceptions: bool = True) -> None:
        method = getattr(self.firestore, method_name, None)
        if method is None:
            return
        try:
            method(*args)
        except Exception:
            if not swallow_exceptions:
                raise
            logger.warning(
                "firestore_signal_write_failed",
                extra={"event": "firestore_signal_write_failed", "context": {"method": method_name}},
            )

    def _execution_costs(self, route: dict) -> dict:
        gas_fee = float(route.get("gas_estimate", 0.0)) / 10_000
        priority_fee_cost = float(route.get("priority_fee", 0.0)) / 1_000_000
        mev_tip = 0.0002 if route.get("private_relay") else 0.0
        return {
            "gas_fee": gas_fee,
            "priority_fee_cost": priority_fee_cost,
            "mev_tip": mev_tip,
        }

    def _degraded_mode(self) -> bool:
        if self.latency_monitor is None:
            return bool(int(self.cache.get("monitor:degraded_mode") or 0))
        return self.latency_monitor.degraded_mode() or bool(int(self.cache.get("monitor:degraded_mode") or 0))

    def _ai_layer_disabled(self) -> bool:
        return bool(self.cache.get("ai:layer_disabled"))

    def _disable_ai_layer(self, reason: str) -> None:
        self.cache.set("ai:layer_disabled", "1", ttl=self.settings.ai_layer_disable_ttl_seconds)
        self.cache.set("ai:layer_disabled_reason", reason, ttl=self.settings.ai_layer_disable_ttl_seconds)

    def _rule_based_inference(
        self,
        snapshot: FeatureSnapshot,
        strategy_decision,
        *,
        fallback_reason: str,
        source_inference: AIInference | None = None,
    ) -> AIInference:
        strategy_signal = strategy_decision.signal if strategy_decision.signal in {"BUY", "SELL"} else "HOLD"
        confidence = float(
            strategy_decision.metadata.get(
                "adjusted_confidence",
                strategy_decision.metadata.get("trade_success_probability", strategy_decision.confidence),
            )
        )
        confidence = max(0.0, min(1.0, confidence))
        expected_risk = float(max(snapshot.volatility, abs(snapshot.atr / max(snapshot.price, 1e-8))))
        direction = 1.0 if strategy_signal == "BUY" else -1.0 if strategy_signal == "SELL" else 0.0
        expected_return = direction * expected_risk * confidence * 0.5
        base_breakdown = dict(source_inference.model_breakdown) if source_inference is not None else {}
        base_breakdown.update(
            {
                "rule_based_confidence": confidence,
                "fallback_reason": 1.0,
            }
        )
        return AIInference(
            price_forecast_return=source_inference.price_forecast_return if source_inference is not None else 0.0,
            expected_return=expected_return,
            expected_risk=expected_risk,
            trade_probability=confidence,
            confidence_score=confidence,
            decision=strategy_signal,
            model_version=f"rule_based_fallback:{strategy_decision.strategy}",
            model_breakdown=base_breakdown,
            reason=f"rule-based fallback triggered: {fallback_reason}",
        )

    async def _inject_sleeve_budget_context(
        self,
        *,
        user_id: str,
        symbol: str,
        snapshot: FeatureSnapshot,
    ) -> None:
        if self.portfolio_ledger is None:
            return
        if not hasattr(self.portfolio_ledger, "portfolio_concentration_profile"):
            return
        try:
            profile = await self.portfolio_ledger.portfolio_concentration_profile(
                user_id,
                candidate_symbol=symbol,
            )
        except Exception:
            return
        symbol_key = str(symbol or "").upper().strip()
        budget_targets = profile.get("factor_sleeve_budget_targets") or {}
        budget_deltas = profile.get("factor_sleeve_budget_deltas") or {}
        sleeve_performance = profile.get("factor_sleeve_performance") or {}
        factor_attribution = profile.get("factor_attribution") or {}
        sleeve = symbol_key if symbol_key in budget_targets else str(
            profile.get("dominant_factor_sleeve") or symbol_key or "UNASSIGNED"
        )
        metrics = dict(sleeve_performance.get(sleeve, {}))
        snapshot.features.update(
            {
                "factor_sleeve_name": sleeve,
                "factor_sleeve_budget_target": float(budget_targets.get(sleeve, 0.0) or 0.0),
                "factor_sleeve_budget_delta": float(budget_deltas.get(sleeve, 0.0) or 0.0),
                "factor_sleeve_actual_share": float(factor_attribution.get(sleeve, 0.0) or 0.0),
                "factor_sleeve_recent_win_rate": float(metrics.get("recent_win_rate", 0.5) or 0.0),
                "factor_sleeve_recent_avg_pnl": float(metrics.get("recent_avg_pnl", 0.0) or 0.0),
                "factor_sleeve_recent_closed_trades": int(metrics.get("recent_closed_trades", 0) or 0),
                "factor_sleeve_budget_turnover": float(profile.get("factor_sleeve_budget_turnover", 0.0) or 0.0),
                "max_factor_sleeve_budget_gap_pct": float(profile.get("max_factor_sleeve_budget_gap_pct", 0.0) or 0.0),
            }
        )

    def _apply_portfolio_context_to_feature_snapshot(
        self,
        *,
        feature_snapshot: dict,
        portfolio_summary: dict,
        symbol: str,
    ) -> None:
        if not feature_snapshot or not portfolio_summary:
            return
        symbol_key = str(symbol or "").upper().strip()
        budget_targets = portfolio_summary.get("factor_sleeve_budget_targets") or {}
        budget_deltas = portfolio_summary.get("factor_sleeve_budget_deltas") or {}
        factor_attribution = portfolio_summary.get("factor_attribution") or {}
        sleeve_performance = portfolio_summary.get("factor_sleeve_performance") or {}
        sleeve = symbol_key if symbol_key in budget_targets else str(
            portfolio_summary.get("dominant_factor_sleeve") or symbol_key or "UNASSIGNED"
        )
        metrics = dict(sleeve_performance.get(sleeve, {}))
        feature_snapshot.update(
            {
                "factor_sleeve_name": sleeve,
                "factor_sleeve_budget_target": float(budget_targets.get(sleeve, 0.0) or 0.0),
                "factor_sleeve_budget_delta": float(budget_deltas.get(sleeve, 0.0) or 0.0),
                "factor_sleeve_actual_share": float(factor_attribution.get(sleeve, 0.0) or 0.0),
                "factor_sleeve_recent_win_rate": float(metrics.get("recent_win_rate", 0.5) or 0.0),
                "factor_sleeve_recent_avg_pnl": float(metrics.get("recent_avg_pnl", 0.0) or 0.0),
                "factor_sleeve_recent_closed_trades": int(metrics.get("recent_closed_trades", 0) or 0),
                "factor_sleeve_budget_turnover": float(portfolio_summary.get("factor_sleeve_budget_turnover", 0.0) or 0.0),
                "max_factor_sleeve_budget_gap_pct": float(portfolio_summary.get("max_factor_sleeve_budget_gap_pct", 0.0) or 0.0),
                "factor_regime": str(portfolio_summary.get("factor_regime", "RANGING") or "RANGING"),
            }
        )

    def _is_micro_capital(self, account_equity: float) -> bool:
        return account_equity <= self.settings.micro_max_capital_threshold

    def _spread_bps(self, order_book: dict) -> float:
        best_bid = float(order_book["bids"][0]["price"]) if order_book.get("bids") else 0.0
        best_ask = float(order_book["asks"][0]["price"]) if order_book.get("asks") else 0.0
        mid = (best_bid + best_ask) / 2 if best_bid and best_ask else 0.0
        return ((best_ask - best_bid) / max(mid, 1e-8) * 10_000) if mid else 0.0

    def _required_tier(self, alpha_score: float) -> str:
        if alpha_score >= 90:
            return "vip"
        if alpha_score >= 80:
            return "pro"
        return "free"

    def _minimum_balance_requirement(self, alpha_score: float) -> float:
        if alpha_score >= 90:
            return max(self.settings.exchange_min_notional * 5, 100.0)
        if alpha_score >= 80:
            return max(self.settings.exchange_min_notional * 2, 25.0)
        return self.settings.exchange_min_notional

    def _allowed_risk_profiles(self, regime: str, volatility: float) -> list[str]:
        if regime.upper() == "VOLATILE" or volatility >= 0.04:
            return ["aggressive"]
        if regime.upper() == "TRENDING":
            return ["moderate", "aggressive"]
        return ["conservative", "moderate", "aggressive"]

    def _force_execution_override_active(self, confidence: float) -> bool:
        return (
            bool(self.settings.force_execution_override_enabled)
            and self.settings.trading_mode == "paper"
            and float(confidence) >= float(self.settings.force_execution_override_confidence_floor)
        )

    def _encode_market_state(self, state: str | None) -> float:
        normalized = str(state or "RANGING").upper()
        mapping = {
            "DUMPING": -1.0,
            "BEARISH": -1.0,
            "RANGING": 0.0,
            "STAGNANT": 0.0,
            "LOW_VOL": 0.25,
            "TRENDING": 1.0,
            "BULLISH": 1.0,
            "HIGH_VOL": 2.0,
            "VOLATILE": 2.0,
        }
        return float(mapping.get(normalized, 0.0))

    def _validate_trade_safety(
        self,
        *,
        symbol: str,
        side: str,
        quantity: float,
        latest_price: float,
        order_book: dict,
        request: TradeRequest,
    ) -> None:
        side_levels = order_book.get("asks", []) if side == "BUY" else order_book.get("bids", [])
        available_quantity = self._available_liquidity(order_book, side)
        liquidity_coverage = available_quantity / max(quantity, 1e-8)
        slippage_plan = self.trade_safety_engine.estimate(order_book, side, quantity)
        volatility = self._trade_volatility(request, latest_price)

        rejection_reasons: list[str] = []
        if slippage_plan["estimated_slippage_bps"] > self.settings.trade_safety_max_slippage_bps:
            rejection_reasons.append(
                f"estimated slippage {slippage_plan['estimated_slippage_bps']:.2f}bps exceeds {self.settings.trade_safety_max_slippage_bps:.2f}bps"
            )
        if not side_levels or liquidity_coverage < self.settings.trade_safety_min_liquidity_coverage_ratio:
            rejection_reasons.append(
                f"liquidity coverage {liquidity_coverage:.2f}x below {self.settings.trade_safety_min_liquidity_coverage_ratio:.2f}x"
            )
        if volatility > self.settings.trade_safety_max_volatility:
            rejection_reasons.append(
                f"volatility {volatility:.4f} exceeds {self.settings.trade_safety_max_volatility:.4f}"
            )

        if not rejection_reasons:
            return

        logger.warning(
            "trade_safety_rejected",
            extra={
                "event": "trade_safety_rejected",
                "context": {
                    "symbol": symbol,
                    "side": side,
                    "quantity": quantity,
                    "estimated_slippage_bps": round(float(slippage_plan["estimated_slippage_bps"]), 4),
                    "liquidity_coverage_ratio": round(float(liquidity_coverage), 4),
                    "volatility": round(float(volatility), 6),
                    "reasons": rejection_reasons,
                },
            },
        )
        self.system_monitor.record_order_outcome("REJECTED")
        raise ValueError(f"Trade safety validation failed: {', '.join(rejection_reasons)}")

    def _available_liquidity(self, order_book: dict, side: str) -> float:
        levels = order_book.get("asks", []) if side == "BUY" else order_book.get("bids", [])
        return sum(float(level.get("qty", 0.0)) for level in levels)

    def _trade_volatility(self, request: TradeRequest, latest_price: float) -> float:
        feature_volatility = float(request.feature_snapshot.get("volatility", request.expected_risk or 0.0))
        atr_value = float(request.feature_snapshot.get("atr", 0.0))
        atr_ratio = atr_value / max(latest_price, 1e-8) if atr_value > 0 else 0.0
        return max(feature_volatility, atr_ratio)

    def _trade_probability_features(
        self,
        snapshot_features: dict[str, float],
        strategy_metadata: dict[str, float | str],
    ) -> dict[str, float]:
        return {
            "trend_strength": float(
                strategy_metadata.get(
                    "trend_strength",
                    snapshot_features.get("15m_adx", 0.0) / 100,
                )
            ),
            "rsi": float(
                strategy_metadata.get(
                    "rsi",
                    snapshot_features.get("15m_rsi", snapshot_features.get("5m_rsi", 50.0)),
                )
            ),
            "breakout_strength": float(strategy_metadata.get("breakout_strength", strategy_metadata.get("base_confidence", 0.0))),
            "volume": math.log1p(
                float(snapshot_features.get("15m_volume", snapshot_features.get("5m_volume", 0.0)))
            ),
        }

    def _extract_probability_features(self, feature_snapshot: dict[str, float]) -> dict[str, float]:
        return {
            "trend_strength": float(feature_snapshot.get("trend_strength", feature_snapshot.get("15m_adx", 0.0) / 100)),
            "rsi": float(feature_snapshot.get("rsi", feature_snapshot.get("15m_rsi", feature_snapshot.get("5m_rsi", 50.0)))),
            "breakout_strength": float(feature_snapshot.get("breakout_strength", feature_snapshot.get("strategy_confidence", 0.0))),
            "volume": float(
                feature_snapshot.get(
                    "volume",
                    math.log1p(float(feature_snapshot.get("15m_volume", feature_snapshot.get("5m_volume", 0.0)))),
                )
            ),
        }

