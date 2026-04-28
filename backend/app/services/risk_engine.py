from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.schemas.trading import AIInference, FeatureSnapshot
from app.trading.risk.manager import TradingRiskDecision, TradingRiskManager


@dataclass
class RiskDecision:
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
class RiskEngine:
    settings: Settings

    def __post_init__(self) -> None:
        self.manager = TradingRiskManager(self.settings)

    def check_global_limits(
        self,
        *,
        drawdown_pct: float,
        trades_this_hour: int,
        asset_exposure_pct: float,
        max_trades_per_hour: int | None = None,
        max_exposure_per_asset: float | None = None,
    ) -> None:
        if drawdown_pct >= self.settings.pause_drawdown_limit:
            raise ValueError("Global drawdown limit reached")
        if trades_this_hour >= (max_trades_per_hour or self.settings.meta_max_trades_per_hour):
            raise ValueError("Global trades-per-hour limit reached")
        if asset_exposure_pct >= (max_exposure_per_asset or self.settings.max_coin_exposure_pct):
            raise ValueError("Global exposure-per-asset limit reached")

    def evaluate(
        self,
        balance: float,
        snapshot: FeatureSnapshot,
        inference: AIInference,
        daily_pnl_pct: float,
        consecutive_losses: int,
        current_coin_exposure: float = 0.0,
        total_pnl_pct: float = 0.0,
        correlation_to_portfolio: float = 0.0,
        alpha_risk_score: float = 0.0,
        hours_since_rebalance: int = 0,
        trade_intelligence_metrics: dict[str, float] | None = None,
        max_capital_allocation_pct: float | None = None,
        daily_loss_limit_override: float | None = None,
        emergency_stop_active: bool = False,
        stop_loss_multiplier: float = 1.0,
    ) -> RiskDecision:
        decision: TradingRiskDecision = self.manager.evaluate(
            balance=balance,
            price=snapshot.price,
            volatility=snapshot.volatility,
            atr=snapshot.atr,
            decision=inference.decision,
            confidence=inference.confidence_score,
            daily_pnl_pct=daily_pnl_pct,
            consecutive_losses=consecutive_losses,
            current_coin_exposure=current_coin_exposure,
            total_pnl_pct=total_pnl_pct,
            correlation_to_portfolio=correlation_to_portfolio,
            alpha_risk_score=alpha_risk_score,
            hours_since_rebalance=hours_since_rebalance,
            regime=snapshot.regime,
            trade_success_probability=inference.trade_probability,
            trade_intelligence_metrics=trade_intelligence_metrics,
            max_capital_allocation_pct=max_capital_allocation_pct,
            daily_loss_limit_override=daily_loss_limit_override,
            emergency_stop_active=emergency_stop_active,
            stop_loss_multiplier=stop_loss_multiplier,
        )
        return RiskDecision(**decision.__dict__)

    def enforce_user_controls(
        self,
        *,
        balance: float,
        requested_notional: float,
        daily_pnl_pct: float,
        max_capital_allocation_pct: float | None = None,
        daily_loss_limit_override: float | None = None,
        emergency_stop_active: bool = False,
    ) -> float:
        if emergency_stop_active:
            raise ValueError("Emergency stop is active for this user")
        effective_daily_loss_limit = min(
            self.settings.daily_loss_limit,
            daily_loss_limit_override if daily_loss_limit_override is not None else self.settings.daily_loss_limit,
        )
        if daily_pnl_pct <= -effective_daily_loss_limit:
            raise ValueError("Daily loss limit reached")
        effective_capital_allocation_pct = min(
            self.settings.max_coin_exposure_pct,
            max_capital_allocation_pct if max_capital_allocation_pct is not None else self.settings.max_coin_exposure_pct,
        )
        return min(requested_notional, balance * effective_capital_allocation_pct)

    def enforce_portfolio_controls(
        self,
        *,
        balance: float,
        requested_notional: float,
        current_portfolio_exposure_pct: float,
        correlation_to_portfolio: float,
        current_symbol_exposure_pct: float = 0.0,
        side: str = "BUY",
        current_side_exposure_pct: float = 0.0,
        current_theme_exposure_pct: float = 0.0,
        current_cluster_exposure_pct: float = 0.0,
        current_beta_bucket_exposure_pct: float = 0.0,
        sleeve_budget_turnover: float = 0.0,
        sleeve_budget_gap_pct: float = 0.0,
    ) -> float:
        if (
            current_portfolio_exposure_pct <= 0
            and current_symbol_exposure_pct <= 0
            and current_side_exposure_pct <= 0
            and current_theme_exposure_pct <= 0
            and current_cluster_exposure_pct <= 0
            and current_beta_bucket_exposure_pct <= 0
        ):
            return float(requested_notional)
        if current_portfolio_exposure_pct >= self.settings.max_portfolio_exposure_pct:
            raise ValueError("Portfolio exposure limit reached")
        if current_side_exposure_pct >= self.settings.max_portfolio_side_exposure_pct:
            raise ValueError("Portfolio side exposure limit reached")
        if current_theme_exposure_pct >= self.settings.max_portfolio_theme_exposure_pct:
            raise ValueError("Portfolio theme exposure limit reached")
        if current_cluster_exposure_pct >= self.settings.max_portfolio_cluster_exposure_pct:
            raise ValueError("Portfolio cluster exposure limit reached")
        if current_beta_bucket_exposure_pct >= self.settings.max_portfolio_beta_bucket_exposure_pct:
            raise ValueError("Portfolio beta bucket exposure limit reached")
        available_notional = balance * max(
            0.0,
            self.settings.max_portfolio_exposure_pct - current_portfolio_exposure_pct,
        )
        available_side_notional = balance * max(
            0.0,
            self.settings.max_portfolio_side_exposure_pct - current_side_exposure_pct,
        )
        available_theme_notional = balance * max(
            0.0,
            self.settings.max_portfolio_theme_exposure_pct - current_theme_exposure_pct,
        )
        available_cluster_notional = balance * max(
            0.0,
            self.settings.max_portfolio_cluster_exposure_pct - current_cluster_exposure_pct,
        )
        available_beta_bucket_notional = balance * max(
            0.0,
            self.settings.max_portfolio_beta_bucket_exposure_pct - current_beta_bucket_exposure_pct,
        )
        capped_notional = min(float(requested_notional), available_notional)
        capped_notional = min(capped_notional, available_side_notional)
        capped_notional = min(capped_notional, available_theme_notional)
        capped_notional = min(capped_notional, available_cluster_notional)
        capped_notional = min(capped_notional, available_beta_bucket_notional)
        if capped_notional <= 0:
            raise ValueError("Portfolio concentration limit reached")

        correlation = max(0.0, min(float(correlation_to_portfolio), 1.0))
        threshold = self.settings.portfolio_correlation_reduce_threshold
        if correlation >= threshold:
            reduction_span = max(1.0 - threshold, 1e-6)
            normalized = min((correlation - threshold) / reduction_span, 1.0)
            multiplier = 1.0 - normalized * (1.0 - self.settings.portfolio_correlation_min_multiplier)
            capped_notional *= max(self.settings.portfolio_correlation_min_multiplier, multiplier)

        if current_symbol_exposure_pct > 0:
            capped_notional *= self.settings.portfolio_same_symbol_penalty

        stress_turnover = max(
            0.0,
            float(sleeve_budget_turnover) / max(self.settings.portfolio_concentration_soft_turnover, 1e-6),
        )
        stress_gap = max(
            0.0,
            float(sleeve_budget_gap_pct) / max(self.settings.portfolio_concentration_soft_alert_drift, 1e-6),
        )
        sleeve_stress = max(stress_turnover, stress_gap)
        if sleeve_stress >= 1.0:
            normalized = min((sleeve_stress - 1.0) / max(sleeve_stress, 1.0), 1.0)
            floor = max(self.settings.portfolio_correlation_min_multiplier, 0.65)
            multiplier = 1.0 - normalized * (1.0 - floor)
            capped_notional *= max(floor, multiplier)

        if capped_notional < self.settings.exchange_min_notional:
            raise ValueError("Portfolio controls reduced trade below minimum notional")
        return capped_notional
