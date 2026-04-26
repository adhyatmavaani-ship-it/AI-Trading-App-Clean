from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.core.metrics import (
    portfolio_beta_bucket_concentration_drift_pct,
    portfolio_cluster_concentration_drift_pct,
    portfolio_cluster_turnover,
    portfolio_factor_sleeve_budget_turnover,
    portfolio_gross_exposure_drift_pct,
    portfolio_gross_exposure_pct,
    portfolio_max_factor_sleeve_budget_gap_pct,
    portfolio_max_beta_bucket_exposure_pct,
    portfolio_max_cluster_exposure_pct,
    portfolio_max_side_exposure_pct,
    portfolio_max_symbol_exposure_pct,
    portfolio_max_theme_exposure_pct,
)
from app.schemas.monitoring import (
    DrawdownStatus,
    ModelStabilityStatus,
    PortfolioConcentrationStatus,
    RolloutStatus,
    SystemHealthResponse,
)
from app.services.redis_cache import RedisCache


@dataclass
class SystemMonitorService:
    settings: Settings
    cache: RedisCache

    def record_latency(self, latency_ms: float) -> None:
        bucket = self.cache.get_json("monitor:latency") or {"samples": []}
        samples = list(bucket.get("samples", []))[-199:]
        samples.append(latency_ms)
        self.cache.set_json("monitor:latency", {"samples": samples}, ttl=self.settings.monitor_state_ttl_seconds)

    def increment_error(self) -> None:
        self.cache.increment("monitor:error_count", ttl=self.settings.monitor_state_ttl_seconds)

    def increment_duplicate(self) -> None:
        self.cache.increment("monitor:duplicate_count", ttl=self.settings.monitor_state_ttl_seconds)

    def record_api_call(self, success: bool) -> None:
        self.cache.increment("monitor:api_total", ttl=self.settings.monitor_state_ttl_seconds)
        if not success:
            self.cache.increment("monitor:api_failures", ttl=self.settings.monitor_state_ttl_seconds)

    def record_redis_latency(self, latency_ms: float) -> None:
        self.cache.set("monitor:redis_latency_ms", str(latency_ms), ttl=self.settings.monitor_state_ttl_seconds)

    def record_signal(self, whale_veto: bool = False, blocked_profitable: bool = False) -> None:
        self.cache.increment("monitor:total_signals", ttl=self.settings.monitor_state_ttl_seconds)
        if whale_veto:
            self.cache.increment("monitor:whale_veto_blocked", ttl=self.settings.monitor_state_ttl_seconds)
        if blocked_profitable:
            self.cache.increment("monitor:blocked_profitable_signals", ttl=self.settings.monitor_state_ttl_seconds)

    def set_active_trades(self, count: int) -> None:
        self.cache.set("monitor:active_trades", str(count), ttl=self.settings.monitor_state_ttl_seconds)

    def record_execution(self, latency_ms: float, slippage_bps: float) -> None:
        self.cache.set("monitor:execution_latency_ms", str(latency_ms), ttl=self.settings.monitor_state_ttl_seconds)
        self.cache.set("monitor:execution_slippage_bps", str(slippage_bps), ttl=self.settings.monitor_state_ttl_seconds)
        if slippage_bps > self.settings.micro_slippage_threshold_bps:
            self.cache.increment("monitor:slippage_spikes", ttl=self.settings.monitor_state_ttl_seconds)
        if latency_ms > self.settings.latency_spike_threshold_ms:
            self.cache.set("monitor:degraded_mode", "1", ttl=self.settings.monitor_state_ttl_seconds)
        else:
            self.cache.set("monitor:degraded_mode", "0", ttl=self.settings.monitor_state_ttl_seconds)

    def record_order_outcome(self, status: str) -> None:
        if status in {"FAILED", "REJECTED", "EXPIRED"}:
            self.cache.increment("monitor:failed_orders", ttl=self.settings.monitor_state_ttl_seconds)
        if status in {"PARTIAL", "PARTIALLY_FILLED"}:
            self.cache.increment("monitor:partial_fills", ttl=self.settings.monitor_state_ttl_seconds)

    def update_portfolio_concentration(self, profile: dict) -> None:
        if not profile:
            return
        portfolio_gross_exposure_pct.set(float(profile.get("gross_exposure_pct", 0.0) or 0.0))
        portfolio_max_symbol_exposure_pct.set(
            max((float(value) for value in (profile.get("symbol_exposure_pct") or {}).values()), default=0.0)
        )
        portfolio_max_side_exposure_pct.set(
            max((float(value) for value in (profile.get("side_exposure_pct") or {}).values()), default=0.0)
        )
        portfolio_max_theme_exposure_pct.set(
            max((float(value) for value in (profile.get("theme_exposure_pct") or {}).values()), default=0.0)
        )
        portfolio_max_cluster_exposure_pct.set(
            max((float(value) for value in (profile.get("cluster_exposure_pct") or {}).values()), default=0.0)
        )
        portfolio_max_beta_bucket_exposure_pct.set(
            max((float(value) for value in (profile.get("beta_bucket_exposure_pct") or {}).values()), default=0.0)
        )
        portfolio_gross_exposure_drift_pct.set(float(profile.get("gross_exposure_drift", 0.0) or 0.0))
        portfolio_cluster_concentration_drift_pct.set(float(profile.get("cluster_concentration_drift", 0.0) or 0.0))
        portfolio_beta_bucket_concentration_drift_pct.set(
            float(profile.get("beta_bucket_concentration_drift", 0.0) or 0.0)
        )
        portfolio_cluster_turnover.set(float(profile.get("cluster_turnover", 0.0) or 0.0))
        portfolio_factor_sleeve_budget_turnover.set(float(profile.get("factor_sleeve_budget_turnover", 0.0) or 0.0))
        portfolio_max_factor_sleeve_budget_gap_pct.set(
            float(profile.get("max_factor_sleeve_budget_gap_pct", 0.0) or 0.0)
        )

    def snapshot(
        self,
        drawdown: DrawdownStatus,
        rollout: RolloutStatus,
        model_stability: ModelStabilityStatus,
    portfolio_concentration: PortfolioConcentrationStatus | None = None,
) -> SystemHealthResponse:
        latency = self.cache.get_json("monitor:latency") or {"samples": []}
        samples = sorted(float(sample) for sample in latency.get("samples", []))
        if samples:
            p50 = samples[len(samples) // 2]
            p95 = samples[min(len(samples) - 1, int(len(samples) * 0.95))]
        else:
            p50 = p95 = 0.0
        portfolio_concentration = portfolio_concentration or PortfolioConcentrationStatus()
        portfolio_gross_exposure_pct.set(float(portfolio_concentration.gross_exposure_pct))
        portfolio_max_symbol_exposure_pct.set(float(portfolio_concentration.max_symbol_exposure_pct))
        portfolio_max_side_exposure_pct.set(float(portfolio_concentration.max_side_exposure_pct))
        portfolio_max_theme_exposure_pct.set(float(portfolio_concentration.max_theme_exposure_pct))
        portfolio_max_cluster_exposure_pct.set(float(portfolio_concentration.max_cluster_exposure_pct))
        portfolio_max_beta_bucket_exposure_pct.set(float(portfolio_concentration.max_beta_bucket_exposure_pct))
        portfolio_gross_exposure_drift_pct.set(float(portfolio_concentration.gross_exposure_drift))
        portfolio_cluster_concentration_drift_pct.set(float(portfolio_concentration.cluster_concentration_drift))
        portfolio_beta_bucket_concentration_drift_pct.set(float(portfolio_concentration.beta_bucket_concentration_drift))
        portfolio_cluster_turnover.set(float(portfolio_concentration.cluster_turnover))
        portfolio_factor_sleeve_budget_turnover.set(float(portfolio_concentration.factor_sleeve_budget_turnover))
        portfolio_max_factor_sleeve_budget_gap_pct.set(float(portfolio_concentration.max_factor_sleeve_budget_gap_pct))
        return SystemHealthResponse(
            trading_mode=self.settings.trading_mode,
            api_status="ok",
            latency_ms_p50=p50,
            latency_ms_p95=p95,
            active_trades=int(self.cache.get("monitor:active_trades") or 0),
            error_count=int(self.cache.get("monitor:error_count") or 0),
            duplicate_signals_blocked=int(self.cache.get("monitor:duplicate_count") or 0),
            total_signals=int(self.cache.get("monitor:total_signals") or 0),
            whale_veto_blocked=int(self.cache.get("monitor:whale_veto_blocked") or 0),
            blocked_profitable_signals=int(self.cache.get("monitor:blocked_profitable_signals") or 0),
            veto_efficiency_ratio=self._veto_efficiency_ratio(),
            execution_latency_ms=float(self.cache.get("monitor:execution_latency_ms") or 0.0),
            execution_slippage_bps=float(self.cache.get("monitor:execution_slippage_bps") or 0.0),
            failed_orders=int(self.cache.get("monitor:failed_orders") or 0),
            partial_fills=int(self.cache.get("monitor:partial_fills") or 0),
            slippage_spikes=int(self.cache.get("monitor:slippage_spikes") or 0),
            degraded_mode=bool(int(self.cache.get("monitor:degraded_mode") or 0)),
            drawdown=drawdown,
            rollout=rollout,
            model_stability=model_stability,
            portfolio_concentration=portfolio_concentration,
        )


    def _veto_efficiency_ratio(self) -> float:
        blocked = int(self.cache.get("monitor:whale_veto_blocked") or 0)
        blocked_profitable = int(self.cache.get("monitor:blocked_profitable_signals") or 0)
        if blocked == 0:
            return 0.0
        return max(0.0, (blocked - blocked_profitable) / blocked)

    def api_success_rate(self) -> float:
        total = int(self.cache.get("monitor:api_total") or 0)
        failures = int(self.cache.get("monitor:api_failures") or 0)
        if total <= 0:
            return 1.0
        return max(0.0, min(1.0, (total - failures) / total))
