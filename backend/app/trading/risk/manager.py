from __future__ import annotations

from dataclasses import dataclass
import math

from app.core.config import Settings
from app.trading.exits import initial_exit_plan


@dataclass
class TradingRiskDecision:
    position_notional: float
    position_size_pct: float
    stop_loss: float
    trailing_stop_pct: float
    risk_budget: float
    atr_stop_distance: float
    risk_level: str
    exposure_pct: float
    correlation_penalty: float
    rebalance_required: bool
    capital_allocation_cap_pct: float


@dataclass
class TradingRiskManager:
    settings: Settings

    def evaluate(
        self,
        *,
        balance: float,
        price: float,
        volatility: float,
        atr: float,
        decision: str,
        confidence: float,
        daily_pnl_pct: float,
        consecutive_losses: int,
        current_coin_exposure: float = 0.0,
        total_pnl_pct: float = 0.0,
        correlation_to_portfolio: float = 0.0,
        alpha_risk_score: float = 0.0,
        hours_since_rebalance: int = 0,
        regime: str = "RANGING",
        trade_success_probability: float | None = None,
        trade_intelligence_metrics: dict[str, float] | None = None,
        max_capital_allocation_pct: float | None = None,
        daily_loss_limit_override: float | None = None,
        emergency_stop_active: bool = False,
        stop_loss_multiplier: float = 1.0,
    ) -> TradingRiskDecision:
        if emergency_stop_active:
            raise ValueError("Emergency stop is active for this user")
        if daily_pnl_pct <= -self.settings.abnormal_loss_limit:
            raise ValueError("Kill switch engaged due to abnormal loss")
        effective_daily_loss_limit = min(
            self.settings.daily_loss_limit,
            daily_loss_limit_override if daily_loss_limit_override is not None else self.settings.daily_loss_limit,
        )
        if daily_pnl_pct <= -effective_daily_loss_limit:
            raise ValueError("Daily loss limit reached")
        if total_pnl_pct <= -self.settings.global_max_capital_loss:
            raise ValueError("Global capital loss limit reached")
        if consecutive_losses >= self.settings.max_consecutive_losses:
            raise ValueError("Trading paused after consecutive losses")

        current_exposure_pct = (
            current_coin_exposure
            if current_coin_exposure <= 1
            else current_coin_exposure / max(balance, 1e-8)
        )
        effective_capital_allocation_pct = min(
            self.settings.max_coin_exposure_pct,
            max_capital_allocation_pct if max_capital_allocation_pct is not None else self.settings.max_coin_exposure_pct,
        )
        if current_exposure_pct >= effective_capital_allocation_pct:
            raise ValueError("Coin exposure limit reached")

        volatility_multiplier = 0.5 if volatility > 0.03 else 1.0
        confidence_multiplier = max(0.4, min(1.4, confidence / 0.65))
        correlation_penalty = (
            0.7
            if correlation_to_portfolio >= self.settings.correlation_penalty_threshold
            else 1.0
        )
        alpha_penalty = max(0.3, 1 - alpha_risk_score)
        probability_multiplier = self._probability_position_multiplier(trade_success_probability)
        regime_multiplier = self._regime_position_multiplier(
            regime=regime,
            confidence=confidence,
            volatility=volatility,
            probability=trade_success_probability,
            trade_intelligence_metrics=trade_intelligence_metrics,
        )
        risk_budget = balance * self.settings.base_risk_per_trade * volatility_multiplier
        risk_budget *= (
            confidence_multiplier
            * correlation_penalty
            * alpha_penalty
            * probability_multiplier
            * regime_multiplier
        )

        exit_plan = initial_exit_plan(
            side=decision,
            entry_price=price,
            atr=atr,
            volatility=volatility,
            stop_loss_multiplier=stop_loss_multiplier,
            take_profit_rr=float(self.settings.strict_trade_min_take_profit_rr),
        )
        atr_stop_distance = max(atr * 1.8 * stop_loss_multiplier, price * 0.004)
        stop_distance = float(exit_plan.stop_distance)
        raw_position_notional = risk_budget / max(stop_distance / max(price, 1e-8), 1e-6)
        volatility_adjustment = max(0.35, 1 - min(volatility, 0.5))
        position_notional = min(
            balance * effective_capital_allocation_pct,
            raw_position_notional * volatility_adjustment,
        )
        if position_notional < self.settings.exchange_min_notional:
            raise ValueError("Position size below minimum trade threshold")
        position_size_pct = position_notional / max(balance, 1e-8)

        current_exposure_notional = current_exposure_pct * balance
        projected_exposure = min(
            1.0,
            (current_exposure_notional + position_notional) / max(balance, 1e-8),
        )
        trailing_stop_pct = float(exit_plan.trailing_stop_pct)
        stop_loss = float(exit_plan.stop_loss)
        risk_level = (
            "HIGH" if volatility > 0.03 else "MEDIUM" if volatility > 0.015 else "LOW"
        )
        rebalance_required = (
            hours_since_rebalance >= self.settings.rebalance_interval_hours
            or projected_exposure > self.settings.max_coin_exposure_pct
        )

        return TradingRiskDecision(
            position_notional=position_notional,
            position_size_pct=position_size_pct,
            stop_loss=stop_loss,
            trailing_stop_pct=trailing_stop_pct,
            risk_budget=risk_budget,
            atr_stop_distance=atr_stop_distance,
            risk_level=risk_level,
            exposure_pct=projected_exposure,
            correlation_penalty=correlation_penalty,
            rebalance_required=rebalance_required,
            capital_allocation_cap_pct=effective_capital_allocation_pct,
        )

    def _regime_position_multiplier(
        self,
        *,
        regime: str,
        confidence: float,
        volatility: float,
        probability: float | None,
        trade_intelligence_metrics: dict[str, float] | None,
    ) -> float:
        normalized_regime = self._normalize_regime(regime)
        bounded_confidence = max(0.0, min(float(confidence), 1.0))
        bounded_probability = max(
            self.settings.probability_position_floor,
            min(float(probability if probability is not None else bounded_confidence), 1.0),
        )
        metrics = trade_intelligence_metrics or {}
        win_rate = max(0.0, min(float(metrics.get("win_rate", 0.5)), 1.0))
        avg_r_multiple = float(metrics.get("avg_r_multiple", 0.0))
        avg_drawdown = max(0.0, float(metrics.get("avg_drawdown", 0.0)))

        confidence_edge = self._clamp01((bounded_confidence - 0.55) / 0.35)
        probability_edge = self._clamp01(
            (bounded_probability - self.settings.trade_probability_threshold)
            / max(1.0 - self.settings.trade_probability_threshold, 1e-6)
        )
        win_rate_score = self._clamp01((win_rate - 0.45) / 0.20)
        r_multiple_score = self._clamp01((avg_r_multiple + 0.25) / 1.25)
        drawdown_penalty = self._clamp01(avg_drawdown / max(self.settings.rolling_drawdown_limit, 1e-6))
        quality_score = (
            0.35 * win_rate_score
            + 0.30 * r_multiple_score
            + 0.20 * probability_edge
            + 0.15 * (1.0 - drawdown_penalty)
        )
        smoothing = max(0.05, min(float(self.settings.regime_position_smoothing), 0.35))

        if normalized_regime == "TRENDING":
            multiplier = (
                1.0
                + self.settings.regime_trending_size_boost * confidence_edge
                + smoothing * probability_edge
                + smoothing * quality_score
            )
            return min(max(multiplier, 0.75), 1.35)

        if normalized_regime == "HIGH_VOL":
            if volatility >= self.settings.regime_high_vol_skip_volatility and (
                probability_edge < 0.35 or quality_score < 0.45
            ):
                raise ValueError("High-volatility regime rejected by dynamic sizing")
            multiplier = (
                self.settings.regime_high_vol_size_multiplier
                + smoothing * 0.5 * confidence_edge
                + smoothing * 0.5 * probability_edge
                + smoothing * 0.5 * quality_score
                - smoothing * drawdown_penalty
            )
            return min(max(multiplier, 0.20), 0.75)

        multiplier = (
            self.settings.regime_ranging_size_multiplier
            + smoothing * 0.35 * confidence_edge
            + smoothing * 0.25 * probability_edge
            + smoothing * 0.20 * quality_score
            - smoothing * 0.40 * drawdown_penalty
        )
        return min(max(multiplier, 0.35), 0.90)

    def _probability_position_multiplier(self, probability: float | None) -> float:
        if probability is None:
            return 1.0
        bounded_probability = self._clamp01(float(probability))
        floor = max(0.05, min(float(self.settings.probability_position_floor), 1.0))
        ceiling = max(1.0, float(self.settings.probability_position_ceiling))
        threshold = self._clamp01(float(self.settings.trade_probability_threshold))
        smoothing = max(0.5, min(float(self.settings.probability_position_smoothing), 3.0))

        if bounded_probability <= threshold:
            normalized = bounded_probability / max(threshold, 1e-6)
            return floor + (1.0 - floor) * math.pow(normalized, smoothing)

        normalized = (bounded_probability - threshold) / max(1.0 - threshold, 1e-6)
        return 1.0 + (ceiling - 1.0) * math.pow(normalized, smoothing)

    def _normalize_regime(self, regime: str) -> str:
        normalized = str(regime or "RANGING").upper()
        if normalized in {"VOLATILE", "HIGH_VOL", "HIGH-VOL"}:
            return "HIGH_VOL"
        if normalized == "TRENDING":
            return "TRENDING"
        return "RANGING"

    def _clamp01(self, value: float) -> float:
        if not math.isfinite(value):
            return 0.0
        return max(0.0, min(value, 1.0))
