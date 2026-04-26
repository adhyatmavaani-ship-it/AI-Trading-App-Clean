from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from time import perf_counter

from app.core.config import Settings
from app.services.drawdown_protection import DrawdownProtectionService
from app.services.redis_state_manager import RedisStateManager
from app.services.risk_engine import RiskEngine
from app.services.system_monitor import SystemMonitorService


@dataclass(frozen=True)
class SystemHealthStatus:
    healthy: bool
    execution_latency_ms: float
    api_success_rate: float
    redis_latency_ms: float
    degraded_mode: bool
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MetaControlDecision:
    allow_trade: bool
    selected_strategy: str
    capital_multiplier: float
    confidence_score: float
    health: SystemHealthStatus
    allocation_action: str = "allocate_capital"
    reasons: list[str] = field(default_factory=list)

    def payload(self) -> dict:
        data = asdict(self)
        data["health"] = asdict(self.health)
        return data


@dataclass
class MetaController:
    settings: Settings
    cache: any
    system_monitor: SystemMonitorService
    drawdown_protection: DrawdownProtectionService
    risk_engine: RiskEngine
    rollout_manager: any
    model_stability: any
    redis_state_manager: RedisStateManager
    firestore: any | None = None
    portfolio_ledger: any | None = None

    def govern_signal(
        self,
        *,
        user_id: str,
        symbol: str,
        side: str,
        proposed_strategy: str,
        volatility: float,
        macro_bias: dict,
        liquidity_stability: float,
        latency_ms: float,
        ai_score: float,
        ai_confidence: float,
        whale_score: float,
        sentiment_score: float,
        regime_type: str = "RANGING",
        trade_intelligence_metrics: dict[str, float] | None = None,
    ) -> MetaControlDecision:
        health = self.system_health_check(user_id=user_id)
        reasons = list(health.reasons)
        if not health.healthy:
            return MetaControlDecision(
                allow_trade=False,
                selected_strategy="NO_TRADE",
                capital_multiplier=0.0,
                confidence_score=0.0,
                health=health,
                allocation_action="skip_trade",
                reasons=reasons or ["System health is unstable"],
            )

        try:
            self.global_risk_limits(user_id=user_id, symbol=symbol)
        except ValueError as exc:
            reasons.append(str(exc))
            return MetaControlDecision(
                allow_trade=False,
                selected_strategy="NO_TRADE",
                capital_multiplier=0.0,
                confidence_score=0.0,
                health=health,
                allocation_action="skip_trade",
                reasons=reasons,
            )

        selected_strategy = self.strategy_selector(
            proposed_strategy=proposed_strategy,
            volatility=volatility,
            macro_bias=macro_bias,
            liquidity_stability=liquidity_stability,
            latency_ms=latency_ms,
        )
        if side == "HOLD":
            reasons.append("No directional edge")
            return MetaControlDecision(
                allow_trade=False,
                selected_strategy="NO_TRADE",
                capital_multiplier=0.0,
                confidence_score=0.0,
                health=health,
                allocation_action="skip_trade",
                reasons=reasons,
            )
        if selected_strategy == "NO_TRADE":
            reasons.append("Strategy selector found no favorable execution path")
            return MetaControlDecision(
                allow_trade=False,
                selected_strategy=selected_strategy,
                capital_multiplier=0.0,
                confidence_score=0.0,
                health=health,
                allocation_action="skip_trade",
                reasons=reasons,
            )

        confidence_gate = self.confidence_gate(
            side=side,
            ai_score=ai_score,
            ai_confidence=ai_confidence,
            whale_score=whale_score,
            sentiment_score=sentiment_score,
            macro_bias=macro_bias,
        )
        reasons.extend(confidence_gate["reasons"])
        sleeve_priority = self._sleeve_priority_overlay(user_id=user_id, symbol=symbol)
        reasons.extend(sleeve_priority["reasons"])
        adjusted_confidence = confidence_gate["confidence_score"] * float(sleeve_priority["confidence_multiplier"])
        if not confidence_gate["allow_trade"]:
            return MetaControlDecision(
                allow_trade=False,
                selected_strategy="NO_TRADE",
                capital_multiplier=0.0,
                confidence_score=adjusted_confidence,
                health=health,
                allocation_action="skip_trade",
                reasons=reasons,
            )
        if adjusted_confidence < 0.52:
            reasons.append("Sleeve quality de-prioritized this setup")
            return MetaControlDecision(
                allow_trade=False,
                selected_strategy="NO_TRADE",
                capital_multiplier=0.0,
                confidence_score=adjusted_confidence,
                health=health,
                allocation_action="skip_trade",
                reasons=reasons,
            )

        allocation = self.capital_allocation(
            user_id=user_id,
            strategy=selected_strategy,
            volatility=volatility,
            macro_bias=macro_bias,
            regime_type=regime_type,
            trade_intelligence_metrics=trade_intelligence_metrics,
            symbol=symbol,
        )
        reasons.extend(allocation["reasons"])
        if allocation["action"] == "skip_trade":
            return MetaControlDecision(
                allow_trade=False,
                selected_strategy="NO_TRADE",
                capital_multiplier=0.0,
                confidence_score=adjusted_confidence,
                health=health,
                allocation_action="skip_trade",
                reasons=reasons,
            )
        return MetaControlDecision(
            allow_trade=True,
            selected_strategy=selected_strategy,
            capital_multiplier=allocation["capital_multiplier"],
            confidence_score=adjusted_confidence,
            health=health,
            allocation_action=allocation["action"],
            reasons=reasons or ["Meta control approved trade"],
        )

    def strategy_selector(
        self,
        *,
        proposed_strategy: str,
        volatility: float,
        macro_bias: dict,
        liquidity_stability: float,
        latency_ms: float,
    ) -> str:
        proposed = (proposed_strategy or "AI").upper()
        macro_regime = str(macro_bias.get("regime", "NEUTRAL")).upper()
        if liquidity_stability < self.settings.meta_min_liquidity_stability:
            return "NO_TRADE"
        if volatility >= self.settings.meta_ai_volatility_ceiling and macro_regime == "BEARISH":
            return "NO_TRADE"
        if (
            latency_ms <= self.settings.meta_health_max_latency_ms
            and volatility <= self.settings.meta_sniper_volatility_ceiling
            and liquidity_stability >= 0.75
            and macro_regime != "BEARISH"
        ):
            return "SNIPER"
        if proposed.startswith("SNIPER") and macro_regime == "BEARISH":
            return "NO_TRADE"
        return "AI"

    def confidence_gate(
        self,
        *,
        side: str,
        ai_score: float,
        ai_confidence: float,
        whale_score: float,
        sentiment_score: float,
        macro_bias: dict,
    ) -> dict:
        normalized_ai_score = ai_score / 100 if ai_score > 1 else ai_score
        macro_regime = str(macro_bias.get("regime", "NEUTRAL")).upper()
        macro_multiplier = float(macro_bias.get("multiplier", 1.0))
        side = side.upper()
        bullish_side = side == "BUY"
        macro_alignment = 0.9 if macro_regime == "BULLISH" and bullish_side else 0.9 if macro_regime == "BEARISH" and not bullish_side else 0.35 if macro_regime in {"BULLISH", "BEARISH"} else 0.6
        weighted_confidence = (
            normalized_ai_score * 0.35
            + ai_confidence * 0.25
            + whale_score * 0.20
            + min(1.0, sentiment_score / 1.5) * 0.10
            + min(1.0, macro_alignment * macro_multiplier) * 0.10
        )
        reasons: list[str] = []
        conflict_score = 0.0
        if macro_regime == "BEARISH" and bullish_side:
            conflict_score += 0.25
            reasons.append("Macro bias is bearish against a long setup")
        if macro_regime == "BULLISH" and not bullish_side:
            conflict_score += 0.20
            reasons.append("Macro bias is bullish against a short setup")
        if bullish_side and whale_score < 0.35:
            conflict_score += 0.15
            reasons.append("Whale participation does not confirm the long")
        if not bullish_side and whale_score > 0.70:
            conflict_score += 0.15
            reasons.append("Whale accumulation conflicts with the short")
        if normalized_ai_score >= 0.70 and weighted_confidence < 0.55:
            conflict_score += 0.15
            reasons.append("Cross-signal confidence is weaker than the model score")
        allow_trade = conflict_score < self.settings.meta_conflict_gate_threshold and weighted_confidence >= 0.55
        if not allow_trade and not reasons:
            reasons.append("Confidence gate rejected the setup")
        return {
            "allow_trade": allow_trade,
            "confidence_score": round(weighted_confidence, 4),
            "reasons": reasons,
        }

    def capital_allocation(
        self,
        *,
        user_id: str,
        strategy: str,
        volatility: float,
        macro_bias: dict,
        regime_type: str = "RANGING",
        trade_intelligence_metrics: dict[str, float] | None = None,
        symbol: str = "",
    ) -> dict[str, float | str | list[str]]:
        strategy = strategy.upper()
        base = 0.9 if strategy == "SNIPER" else 1.0
        if volatility >= self.settings.meta_sniper_volatility_ceiling:
            base *= self.settings.meta_risk_reduction_multiplier
        if str(macro_bias.get("regime", "NEUTRAL")).upper() == "BEARISH":
            base *= self.settings.meta_bearish_macro_multiplier
        streak = int(self.cache.get(f"meta:win_streak:{user_id}") or 0)
        boost = min(self.settings.meta_max_capital_boost, 1.0 + streak * self.settings.meta_winning_streak_step)
        drawdown_state = self.drawdown_protection.load(user_id).state
        stability = self.model_stability.load_status()
        if drawdown_state == "REDUCED":
            base *= self.settings.drawdown_reduction_factor
        base *= stability.trading_frequency_multiplier
        overlay = self._trade_quality_overlay(
            regime_type=regime_type,
            trade_intelligence_metrics=trade_intelligence_metrics,
        )
        reasons = list(overlay["reasons"])
        action = str(overlay["action"])
        if action == "skip_trade":
            return {
                "capital_multiplier": 0.0,
                "action": action,
                "reasons": reasons,
            }
        concentration_overlay = self._concentration_overlay(user_id=user_id, symbol=symbol)
        reasons.extend(concentration_overlay["reasons"])
        if str(concentration_overlay["action"]) == "skip_trade":
            return {
                "capital_multiplier": 0.0,
                "action": "skip_trade",
                "reasons": reasons,
            }
        sleeve_rotation = self._sleeve_rotation_overlay(user_id=user_id, symbol=symbol)
        reasons.extend(sleeve_rotation["reasons"])
        if str(sleeve_rotation["action"]) == "skip_trade":
            return {
                "capital_multiplier": 0.0,
                "action": "skip_trade",
                "reasons": reasons,
            }
        capital_multiplier = base * boost * float(overlay["capital_multiplier"])
        capital_multiplier *= float(concentration_overlay["capital_multiplier"])
        capital_multiplier *= float(sleeve_rotation["capital_multiplier"])
        if action == "reduce_size" or str(concentration_overlay["action"]) == "reduce_size":
            capital_multiplier = min(0.99, capital_multiplier)
        if str(sleeve_rotation["action"]) == "reduce_size":
            capital_multiplier = min(0.99, capital_multiplier)
        capital_multiplier = max(
            self.settings.meta_min_capital_multiplier,
            min(self.settings.meta_max_capital_boost, capital_multiplier),
        )
        final_action = action
        if str(concentration_overlay["action"]) == "reduce_size" or str(sleeve_rotation["action"]) == "reduce_size":
            final_action = "reduce_size"
        return {
            "capital_multiplier": round(capital_multiplier, 4),
            "action": final_action,
            "reasons": reasons,
        }

    def _trade_quality_overlay(
        self,
        *,
        regime_type: str,
        trade_intelligence_metrics: dict[str, float] | None,
    ) -> dict[str, float | str | list[str]]:
        metrics = trade_intelligence_metrics or {}
        reasons: list[str] = []
        regime = str(regime_type or "RANGING").upper()
        if not metrics:
            reasons.append(f"{regime} regime intelligence is limited; using conservative capital")
            return {"capital_multiplier": 0.85, "action": "reduce_size", "reasons": reasons}
        win_rate = max(0.0, min(float(metrics.get("win_rate", 0.5)), 1.0))
        avg_r_multiple = float(metrics.get("avg_r_multiple", 0.0))
        avg_drawdown = max(0.0, float(metrics.get("avg_drawdown", 0.0)))

        if win_rate < self.settings.meta_regime_min_win_rate:
            reasons.append(f"{regime} regime win rate is below policy")
            return {"capital_multiplier": 0.0, "action": "skip_trade", "reasons": reasons}
        if avg_r_multiple <= self.settings.meta_regime_min_r_multiple:
            reasons.append(f"{regime} regime expectancy is non-positive")
            return {"capital_multiplier": 0.0, "action": "skip_trade", "reasons": reasons}
        if avg_drawdown >= self.settings.meta_regime_drawdown_hard_limit:
            reasons.append(f"{regime} regime drawdown risk is too high")
            return {"capital_multiplier": 0.0, "action": "skip_trade", "reasons": reasons}

        win_rate_score = self._clamp01(
            (win_rate - self.settings.meta_regime_min_win_rate)
            / max(self.settings.meta_regime_target_win_rate - self.settings.meta_regime_min_win_rate, 1e-6)
        )
        r_multiple_score = self._clamp01(
            (avg_r_multiple - self.settings.meta_regime_min_r_multiple)
            / max(self.settings.meta_regime_target_r_multiple - self.settings.meta_regime_min_r_multiple, 1e-6)
        )
        drawdown_score = 1.0 - self._clamp01(
            avg_drawdown / max(self.settings.meta_regime_drawdown_soft_limit, 1e-6)
        )
        quality_score = 0.45 * win_rate_score + 0.35 * r_multiple_score + 0.20 * drawdown_score
        multiplier = 0.55 + quality_score * 0.70

        if avg_drawdown >= self.settings.meta_regime_drawdown_soft_limit:
            reasons.append(f"{regime} regime drawdown is elevated; reducing size")
            multiplier *= 0.75
        if quality_score < 0.45:
            reasons.append(f"{regime} regime quality is mediocre; reducing size")
            return {"capital_multiplier": multiplier, "action": "reduce_size", "reasons": reasons}
        reasons.append(f"{regime} regime quality supports capital allocation")
        return {"capital_multiplier": multiplier, "action": "allocate_capital", "reasons": reasons}

    def _clamp01(self, value: float) -> float:
        return max(0.0, min(value, 1.0))

    def _concentration_overlay(self, *, user_id: str, symbol: str) -> dict[str, float | str | list[str]]:
        if self.portfolio_ledger is None or not hasattr(self.portfolio_ledger, "latest_concentration_profile"):
            return {"capital_multiplier": 1.0, "action": "allocate_capital", "reasons": []}
        profile = self.portfolio_ledger.latest_concentration_profile(user_id)
        if not profile:
            return {"capital_multiplier": 1.0, "action": "allocate_capital", "reasons": []}

        pressures = {
            "gross exposure": float(profile.get("gross_exposure_pct", 0.0)) / max(self.settings.max_portfolio_exposure_pct, 1e-8),
            "theme concentration": float(profile.get("candidate_theme_exposure_pct", 0.0)) / max(self.settings.max_portfolio_theme_exposure_pct, 1e-8),
            "cluster concentration": max((float(value) for value in (profile.get("cluster_exposure_pct") or {}).values()), default=0.0)
            / max(self.settings.max_portfolio_cluster_exposure_pct, 1e-8),
            "beta concentration": max((float(value) for value in (profile.get("beta_bucket_exposure_pct") or {}).values()), default=0.0)
            / max(self.settings.max_portfolio_beta_bucket_exposure_pct, 1e-8),
        }
        drift_pressure = max(
            0.0,
            abs(float(profile.get("gross_exposure_drift", 0.0))),
            abs(float(profile.get("cluster_concentration_drift", 0.0))),
            abs(float(profile.get("beta_bucket_concentration_drift", 0.0))),
        )
        turnover_pressure = self._clamp01(float(profile.get("cluster_turnover", 0.0)) / 0.40)
        max_pressure = max(pressures.values(), default=0.0)
        hottest_pressure = max(pressures, key=pressures.get) if pressures else "portfolio concentration"
        sleeve_pressure = max((float(value) for value in (profile.get("factor_attribution") or {}).values()), default=0.0)
        dominant_sleeve = str(profile.get("dominant_factor_sleeve") or "dominant sleeve")
        sleeve_performance = dict((profile.get("factor_sleeve_performance") or {}).get(dominant_sleeve, {}))
        recent_win_rate = float(sleeve_performance.get("recent_win_rate", sleeve_performance.get("win_rate", 0.5)) or 0.0)
        recent_realized_pnl = float(
            sleeve_performance.get("recent_realized_pnl", sleeve_performance.get("realized_pnl", 0.0)) or 0.0
        )
        reasons: list[str] = []
        if sleeve_pressure >= self.settings.meta_factor_sleeve_hard_limit:
            reasons.append(f"{dominant_sleeve} is dominating factor exposure too aggressively")
            return {"capital_multiplier": 0.0, "action": "skip_trade", "reasons": reasons}
        if max_pressure >= self.settings.meta_concentration_hard_limit_ratio:
            reasons.append(f"{hottest_pressure.capitalize()} is too high for {symbol.upper() or 'this trade'}")
            return {"capital_multiplier": 0.0, "action": "skip_trade", "reasons": reasons}
        soft_band = self.settings.meta_concentration_soft_limit_ratio
        hard_band = max(self.settings.meta_concentration_hard_limit_ratio, soft_band + 0.01)
        reduction_band = soft_band * 0.75
        drift_ratio = self._clamp01(drift_pressure / 0.05) if drift_pressure > 0 else 0.0
        pressure_score = max(max_pressure, drift_ratio, turnover_pressure)
        if pressure_score >= reduction_band:
            reasons.append(f"{hottest_pressure.capitalize()} is elevated; softening capital allocation")
            span = max(hard_band - reduction_band, 1e-6)
            scaled = self._clamp01((pressure_score - reduction_band) / span)
            multiplier_floor = float(self.settings.meta_concentration_reduction_multiplier)
            multiplier = 1.0 - scaled * (1.0 - multiplier_floor)
            if sleeve_pressure >= self.settings.meta_factor_sleeve_soft_limit:
                reasons.append(f"{dominant_sleeve} is crowding the factor book")
                multiplier *= 0.9
                if recent_realized_pnl < 0.0 or recent_win_rate < self.settings.meta_factor_sleeve_recent_win_rate_floor:
                    reasons.append(f"{dominant_sleeve} sleeve is deteriorating recently")
                    multiplier *= 0.85
                elif recent_realized_pnl > 0.0 and recent_win_rate >= 0.55:
                    reasons.append(f"{dominant_sleeve} sleeve is still earning despite crowding")
                    multiplier = min(0.99, multiplier * 1.05)
            if drift_pressure > 0.03:
                reasons.append("Recent concentration drift is rising")
            if float(profile.get("cluster_turnover", 0.0)) > 0.25:
                reasons.append("Cluster composition is turning over quickly")
            return {"capital_multiplier": multiplier, "action": "reduce_size", "reasons": reasons}
        return {"capital_multiplier": 1.0, "action": "allocate_capital", "reasons": reasons}

    def _sleeve_rotation_overlay(self, *, user_id: str, symbol: str) -> dict[str, float | str | list[str]]:
        if self.portfolio_ledger is None or not hasattr(self.portfolio_ledger, "latest_concentration_profile"):
            return {"capital_multiplier": 1.0, "action": "allocate_capital", "reasons": []}
        profile = self.portfolio_ledger.latest_concentration_profile(user_id)
        if not profile:
            return {"capital_multiplier": 1.0, "action": "allocate_capital", "reasons": []}

        symbol_key = str(symbol or "").upper().strip()
        factor_attribution = profile.get("factor_attribution") or {}
        sleeve = symbol_key if symbol_key in factor_attribution else str(profile.get("dominant_factor_sleeve") or symbol_key or "UNASSIGNED")
        sleeve_metrics = dict((profile.get("factor_sleeve_performance") or {}).get(sleeve, {}))
        if not sleeve_metrics:
            return {"capital_multiplier": 1.0, "action": "allocate_capital", "reasons": []}

        recent_win_rate = float(sleeve_metrics.get("recent_win_rate", 0.5) or 0.0)
        recent_avg_pnl = float(sleeve_metrics.get("recent_avg_pnl", 0.0) or 0.0)
        recent_realized_pnl = float(sleeve_metrics.get("recent_realized_pnl", 0.0) or 0.0)
        recent_trades = int(sleeve_metrics.get("recent_closed_trades", 0) or 0)
        sleeve_pressure = float(factor_attribution.get(sleeve, 0.0) or 0.0)

        has_recent_quality = any(
            key in sleeve_metrics
            for key in ("recent_win_rate", "recent_avg_pnl", "recent_realized_pnl")
        )
        if recent_trades < 3 and not has_recent_quality:
            return {"capital_multiplier": 1.0, "action": "allocate_capital", "reasons": []}

        reasons: list[str] = []
        if (
            sleeve_pressure >= self.settings.meta_factor_sleeve_soft_limit
            and recent_win_rate <= self.settings.meta_factor_sleeve_skip_win_rate
            and recent_avg_pnl <= self.settings.meta_factor_sleeve_skip_avg_pnl
        ):
            reasons.append(f"{sleeve} sleeve is crowded and deteriorating; rotating capital away")
            return {"capital_multiplier": 0.0, "action": "skip_trade", "reasons": reasons}

        quality_score = (
            0.55 * self._clamp01(recent_win_rate)
            + 0.45 * self._clamp01((recent_avg_pnl + 0.02) / 0.04)
        )
        if sleeve_pressure >= self.settings.meta_factor_sleeve_soft_limit:
            reasons.append(f"{sleeve} sleeve pressure is elevated; rotating capital selectively")
            if recent_realized_pnl > 0.0 and recent_win_rate >= 0.55:
                multiplier = min(self.settings.meta_factor_sleeve_rotation_boost, 0.92 + quality_score * 0.16)
                reasons.append(f"{sleeve} sleeve remains one of the stronger recent sleeves")
                return {"capital_multiplier": multiplier, "action": "allocate_capital", "reasons": reasons}
            multiplier = max(
                self.settings.meta_factor_sleeve_rotation_floor,
                0.9 - ((1.0 - quality_score) * 0.35),
            )
            reasons.append(f"{sleeve} sleeve is losing recent quality; reducing budget")
            return {"capital_multiplier": multiplier, "action": "reduce_size", "reasons": reasons}

        if recent_realized_pnl > 0.0 and recent_win_rate >= 0.60:
            reasons.append(f"{sleeve} sleeve is attracting more recent capital support")
            multiplier = min(self.settings.meta_factor_sleeve_rotation_boost, 1.0 + ((quality_score - 0.5) * 0.12))
            return {"capital_multiplier": multiplier, "action": "allocate_capital", "reasons": reasons}
        return {"capital_multiplier": 1.0, "action": "allocate_capital", "reasons": reasons}

    def _sleeve_priority_overlay(self, *, user_id: str, symbol: str) -> dict[str, float | list[str]]:
        if self.portfolio_ledger is None or not hasattr(self.portfolio_ledger, "latest_concentration_profile"):
            return {"confidence_multiplier": 1.0, "reasons": []}
        profile = self.portfolio_ledger.latest_concentration_profile(user_id)
        if not profile:
            return {"confidence_multiplier": 1.0, "reasons": []}

        symbol_key = str(symbol or "").upper().strip()
        budget_targets = profile.get("factor_sleeve_budget_targets") or {}
        budget_deltas = profile.get("factor_sleeve_budget_deltas") or {}
        sleeve_metrics_map = profile.get("factor_sleeve_performance") or {}
        sleeve = symbol_key if symbol_key in budget_targets else str(profile.get("dominant_factor_sleeve") or symbol_key or "UNASSIGNED")
        target_share = float(budget_targets.get(sleeve, 0.0) or 0.0)
        budget_delta = float(budget_deltas.get(sleeve, 0.0) or 0.0)
        sleeve_metrics = dict(sleeve_metrics_map.get(sleeve, {}))
        recent_win_rate = float(sleeve_metrics.get("recent_win_rate", 0.5) or 0.0)
        recent_avg_pnl = float(sleeve_metrics.get("recent_avg_pnl", 0.0) or 0.0)
        recent_trades = int(sleeve_metrics.get("recent_closed_trades", 0) or 0)
        budget_turnover = float(profile.get("factor_sleeve_budget_turnover", 0.0) or 0.0)
        budget_gap = float(profile.get("max_factor_sleeve_budget_gap_pct", 0.0) or 0.0)
        if target_share <= 0.0 or recent_trades < 3:
            return {"confidence_multiplier": 1.0, "reasons": []}

        reasons: list[str] = []
        if (
            budget_turnover >= self.settings.portfolio_concentration_soft_turnover
            or budget_gap >= self.settings.portfolio_concentration_soft_alert_drift
        ):
            reasons.append(f"{sleeve} sleeve rotation is unstable; priority boost suppressed")
            return {"confidence_multiplier": 1.0, "reasons": reasons}
        if budget_delta > 0.05 and recent_win_rate >= 0.55 and recent_avg_pnl > 0.0:
            reasons.append(f"{sleeve} sleeve has earned more budget priority")
            return {
                "confidence_multiplier": min(
                    self.settings.meta_factor_sleeve_priority_boost,
                    1.0 + (budget_delta * 0.5),
                ),
                "reasons": reasons,
            }
        if budget_delta < -0.05 and (
            recent_win_rate < self.settings.meta_factor_sleeve_recent_win_rate_floor
            or recent_avg_pnl < 0.0
        ):
            reasons.append(f"{sleeve} sleeve has fallen behind budget quality expectations")
            return {
                "confidence_multiplier": max(
                    self.settings.meta_factor_sleeve_priority_floor,
                    1.0 + (budget_delta * 0.6),
                ),
                "reasons": reasons,
            }
        return {"confidence_multiplier": 1.0, "reasons": reasons}

    def system_health_check(self, *, user_id: str) -> SystemHealthStatus:
        drawdown = self.drawdown_protection.load(user_id)
        rollout = self.rollout_manager.status()
        stability = self.model_stability.load_status()
        snapshot = self.system_monitor.snapshot(drawdown=drawdown, rollout=rollout, model_stability=stability)
        redis_latency_ms = self._redis_probe_latency_ms()
        api_success_rate = self.system_monitor.api_success_rate()
        reasons: list[str] = []
        if snapshot.degraded_mode:
            reasons.append("Execution path is in degraded mode")
        if max(snapshot.execution_latency_ms, snapshot.latency_ms_p95) > self.settings.meta_health_max_latency_ms:
            reasons.append("Latency threshold exceeded")
        if api_success_rate < self.settings.meta_health_min_api_success_rate:
            reasons.append("API success rate fell below threshold")
        if redis_latency_ms > self.settings.meta_health_max_redis_latency_ms:
            reasons.append("Redis latency is unstable")
        if stability.degraded:
            reasons.append("Model stability is degraded")
        elif stability.trading_frequency_multiplier < 1.0:
            reasons.append("Model inputs are unstable; trading frequency reduced")
        healthy = not reasons
        return SystemHealthStatus(
            healthy=healthy,
            execution_latency_ms=max(snapshot.execution_latency_ms, snapshot.latency_ms_p95),
            api_success_rate=api_success_rate,
            redis_latency_ms=redis_latency_ms,
            degraded_mode=snapshot.degraded_mode,
            reasons=reasons,
        )

    def global_risk_limits(self, *, user_id: str, symbol: str) -> None:
        drawdown = self.drawdown_protection.load(user_id)
        trades_this_hour = int(self.cache.get(self._trade_count_key(user_id)) or 0)
        asset_exposure_pct = self._asset_exposure_pct(user_id=user_id, symbol=symbol, equity=drawdown.current_equity)
        self.risk_engine.check_global_limits(
            drawdown_pct=drawdown.rolling_drawdown,
            trades_this_hour=trades_this_hour,
            asset_exposure_pct=asset_exposure_pct,
            max_trades_per_hour=self.settings.meta_max_trades_per_hour,
            max_exposure_per_asset=self.settings.max_coin_exposure_pct,
        )

    def record_trade_open(self, *, user_id: str, symbol: str, notional: float) -> None:
        self.cache.increment(self._trade_count_key(user_id), ttl=3600)
        exposure_key = self._exposure_key(user_id, symbol)
        exposure = float(self.cache.get(exposure_key) or 0.0) + float(notional)
        self.cache.set(exposure_key, str(round(exposure, 8)), ttl=self.settings.monitor_state_ttl_seconds)

    def record_trade_outcome(self, *, user_id: str, active_trade: dict, pnl: float) -> None:
        symbol = str(active_trade.get("symbol") or "").upper()
        notional = float(active_trade.get("notional") or 0.0)
        if symbol:
            exposure_key = self._exposure_key(user_id, symbol)
            exposure = max(0.0, float(self.cache.get(exposure_key) or 0.0) - notional)
            self.cache.set(exposure_key, str(round(exposure, 8)), ttl=self.settings.monitor_state_ttl_seconds)
        streak_key = f"meta:win_streak:{user_id}"
        streak = int(self.cache.get(streak_key) or 0)
        updated_streak = max(0, streak + 1) if pnl > 0 else 0
        self.cache.set(streak_key, str(updated_streak), ttl=self.settings.monitor_state_ttl_seconds)
        trade_id = str(active_trade.get("trade_id") or "")
        if trade_id:
            self._update_strategy_analytics(
                strategy=str(active_trade.get("meta_strategy") or active_trade.get("strategy") or "UNKNOWN"),
                confidence_score=float(active_trade.get("meta_confidence_score") or active_trade.get("confidence") or 0.0),
                pnl=pnl,
                blocked=False,
                count_trade=False,
            )
            decision_log = self.get_decision_log(trade_id)
            if decision_log is not None:
                decision_log["outcome"] = {
                    "pnl": pnl,
                    "won": pnl > 0,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                self._persist_decision_log(trade_id, decision_log)

    def log_decision(
        self,
        *,
        trade_id: str,
        user_id: str,
        symbol: str,
        decision: MetaControlDecision,
        signals: dict,
        conflicts: list[str],
        risk_adjustments: dict,
        reason: str,
    ) -> dict:
        payload = {
            "trade_id": trade_id,
            "user_id": user_id,
            "symbol": symbol.upper(),
            "decision": "APPROVED" if decision.allow_trade else "BLOCKED",
            "strategy": decision.selected_strategy,
            "confidence": decision.confidence_score,
            "signals": signals,
            "conflicts": conflicts,
            "risk_adjustments": risk_adjustments,
            "system_health_snapshot": asdict(decision.health),
            "reason": reason,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._persist_decision_log(trade_id, payload)
        self._update_strategy_analytics(
            strategy=decision.selected_strategy,
            confidence_score=decision.confidence_score,
            pnl=None,
            blocked=not decision.allow_trade,
            reasons=conflicts or decision.reasons,
        )
        return payload

    def log_blocked_trade(
        self,
        *,
        trade_id: str,
        user_id: str,
        symbol: str,
        proposed_strategy: str,
        reason: str,
        signals: dict,
        conflicts: list[str],
    ) -> dict:
        health = self.system_health_check(user_id=user_id)
        payload = {
            "trade_id": trade_id,
            "user_id": user_id,
            "symbol": symbol.upper(),
            "decision": "BLOCKED",
            "strategy": proposed_strategy,
            "confidence": float(signals.get("confidence", 0.0)),
            "signals": signals,
            "conflicts": conflicts,
            "risk_adjustments": {"capital_multiplier": 0.0},
            "system_health_snapshot": asdict(health),
            "reason": reason,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._persist_decision_log(trade_id, payload)
        self._update_strategy_analytics(
            strategy=proposed_strategy,
            confidence_score=float(signals.get("confidence", 0.0)),
            pnl=None,
            blocked=True,
            reasons=conflicts or [reason],
        )
        return payload

    def get_decision_log(self, trade_id: str) -> dict | None:
        payload = self.cache.get_json(self._decision_key(trade_id))
        if payload:
            return payload
        if self.firestore is not None and getattr(self.firestore, "client", None) is not None and hasattr(self.firestore, "load_meta_decision"):
            return self.firestore.load_meta_decision(trade_id)
        return None

    def analytics_snapshot(self) -> dict:
        return self.cache.get_json("meta:analytics") or {
            "blocked_trades": {"total": 0, "reasons": {}},
            "strategy_performance": {},
            "confidence_distribution": {},
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _asset_exposure_pct(self, *, user_id: str, symbol: str, equity: float) -> float:
        cached_notional = float(self.cache.get(self._exposure_key(user_id, symbol)) or 0.0)
        if cached_notional <= 0:
            for trade in self.redis_state_manager.restore_active_trades():
                if trade.get("user_id") == user_id and str(trade.get("symbol", "")).upper() == symbol.upper():
                    cached_notional += float(trade.get("notional") or 0.0)
        return min(1.0, cached_notional / max(equity, 1e-8))

    def _trade_count_key(self, user_id: str) -> str:
        return f"meta:trades:{user_id}:{datetime.now(timezone.utc).strftime('%Y%m%d%H')}"

    def _exposure_key(self, user_id: str, symbol: str) -> str:
        return f"meta:exposure:{user_id}:{symbol.upper()}"

    def _decision_key(self, trade_id: str) -> str:
        return f"meta:decision:{trade_id}"

    def _redis_probe_latency_ms(self) -> float:
        started = perf_counter()
        self.cache.get("meta:redis_probe")
        elapsed_ms = (perf_counter() - started) * 1000
        self.cache.set("meta:redis_probe", datetime.now(timezone.utc).isoformat(), ttl=self.settings.monitor_state_ttl_seconds)
        self.system_monitor.record_redis_latency(elapsed_ms)
        return elapsed_ms

    def _persist_decision_log(self, trade_id: str, payload: dict) -> None:
        self.cache.set_json(self._decision_key(trade_id), payload, ttl=self.settings.monitor_state_ttl_seconds)
        if self.firestore is not None and getattr(self.firestore, "client", None) is not None:
            if hasattr(self.firestore, "save_meta_decision"):
                self.firestore.save_meta_decision(trade_id, payload)
            elif hasattr(self.firestore, "save_performance_snapshot"):
                self.firestore.save_performance_snapshot(f"meta-decision:{trade_id}", payload)

    def _update_strategy_analytics(
        self,
        *,
        strategy: str,
        confidence_score: float,
        pnl: float | None,
        blocked: bool,
        count_trade: bool = True,
        reasons: list[str] | None = None,
    ) -> None:
        analytics = self.analytics_snapshot()
        if blocked:
            analytics["blocked_trades"]["total"] = int(analytics["blocked_trades"].get("total", 0)) + 1
            for reason in reasons or ["unknown"]:
                analytics["blocked_trades"]["reasons"][reason] = int(analytics["blocked_trades"]["reasons"].get(reason, 0)) + 1
        strategy_bucket = analytics["strategy_performance"].setdefault(
            strategy,
            {"trades": 0, "wins": 0, "losses": 0, "blocked": 0, "pnl": 0.0},
        )
        if blocked:
            strategy_bucket["blocked"] += 1
        else:
            if count_trade:
                strategy_bucket["trades"] += 1
            if pnl is not None:
                strategy_bucket["wins"] += int(pnl > 0)
                strategy_bucket["losses"] += int(pnl < 0)
                strategy_bucket["pnl"] = round(float(strategy_bucket["pnl"]) + pnl, 8)
        confidence_bucket = analytics["confidence_distribution"]
        bucket = self._confidence_bucket(confidence_score)
        confidence_bucket[bucket] = int(confidence_bucket.get(bucket, 0)) + 1
        analytics["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.cache.set_json("meta:analytics", analytics, ttl=self.settings.monitor_state_ttl_seconds)
        if self.firestore is not None and getattr(self.firestore, "client", None) is not None:
            if hasattr(self.firestore, "save_meta_analytics"):
                self.firestore.save_meta_analytics(analytics)
            elif hasattr(self.firestore, "save_performance_snapshot"):
                self.firestore.save_performance_snapshot("meta:analytics", analytics)

    def _confidence_bucket(self, confidence_score: float) -> str:
        normalized = confidence_score * 100 if confidence_score <= 1 else confidence_score
        if normalized < 50:
            return "0_49"
        if normalized < 65:
            return "50_64"
        if normalized < 80:
            return "65_79"
        return "80_100"

