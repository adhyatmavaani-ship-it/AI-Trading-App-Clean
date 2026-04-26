from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.config import Settings
from app.services.redis_cache import RedisCache


@dataclass
class MicroModeController:
    settings: Settings
    cache: RedisCache

    def evaluate_signal(
        self,
        *,
        user_id: str,
        account_equity: float,
        alpha_score: float,
        whale_conflict: bool,
        net_expected_return: float,
        total_cost: float,
        slippage_bps: float,
        liquidity_stability: float,
        spread_bps: float,
        strategy: str,
        degraded_mode: bool,
        volume: float,
    ) -> dict:
        allowed = True
        reasons: list[str] = []
        if degraded_mode:
            allowed = False
            reasons.append("degraded_mode")
        if alpha_score < self.settings.micro_min_alpha_score:
            allowed = False
            reasons.append("alpha_below_micro_threshold")
        if whale_conflict:
            allowed = False
            reasons.append("whale_veto")
        if net_expected_return <= max(total_cost, self.settings.min_net_profit_threshold):
            allowed = False
            reasons.append("net_profit_below_costs")
        if slippage_bps >= self.settings.micro_slippage_threshold_bps:
            allowed = False
            reasons.append("slippage_too_high")
        if liquidity_stability < 0.45:
            allowed = False
            reasons.append("liquidity_insufficient")
        if volume < 100_000:
            allowed = False
            reasons.append("low_volume")
        if spread_bps > 80:
            allowed = False
            reasons.append("high_spread")
        if strategy not in {"TREND_FOLLOW", "BREAKOUT"}:
            allowed = False
            reasons.append("strategy_not_micro_preferred")
        if not self._within_daily_trade_limit(user_id, account_equity):
            allowed = False
            reasons.append("daily_trade_limit")
        if self._cooldown_active(user_id):
            allowed = False
            reasons.append("loss_cooldown")
        if self._daily_loss_exceeded(user_id, account_equity):
            allowed = False
            reasons.append("daily_loss_limit")
        return {"allowed": allowed, "reasons": reasons}

    def determine_trade_size(
        self,
        *,
        user_id: str,
        account_equity: float,
        latest_price: float,
        requested_notional: float | None,
        slippage_bps: float,
    ) -> dict:
        if account_equity < self.settings.micro_single_trade_capital_threshold:
            base_fraction = 0.90 - min(0.20, slippage_bps / 1000)
            trade_notional = account_equity * max(0.70, base_fraction)
            mode = "single_trade"
        else:
            trade_notional = requested_notional or account_equity * 0.02
            mode = "risk_budget"

        if self._abnormal_slippage(user_id):
            trade_notional *= 0.5

        minimum = self.settings.exchange_min_notional
        if trade_notional < minimum:
            return {
                "skip": True,
                "reason": "below_exchange_minimum",
                "trade_notional": trade_notional,
                "quantity": 0.0,
                "mode": mode,
            }

        quantity = trade_notional / max(latest_price, 1e-8)
        return {
            "skip": False,
            "trade_notional": trade_notional,
            "quantity": quantity,
            "mode": mode,
        }

    def record_trade_open(self, user_id: str) -> None:
        key = self._daily_key(user_id, "trades")
        self.cache.increment(key, ttl=self.settings.monitor_state_ttl_seconds)

    def record_trade_outcome(
        self,
        user_id: str,
        *,
        account_equity: float,
        expected_return: float,
        actual_pnl: float,
        expected_slippage_bps: float,
        actual_slippage_bps: float,
        latency_ms: float,
        execution_success: bool,
        live_notional: float,
    ) -> dict:
        alpha_realization_ratio = actual_pnl / max(expected_return * max(live_notional, 1e-8), 1e-8)
        slippage_error = actual_slippage_bps - expected_slippage_bps
        execution_efficiency = 1.0 if execution_success else 0.0
        execution_efficiency *= max(0.0, 1 - max(0.0, slippage_error) / max(self.settings.micro_slippage_threshold_bps, 1))
        execution_efficiency *= max(0.0, 1 - latency_ms / max(self.settings.latency_spike_threshold_ms * 4, 1))
        daily_pnl_key = self._daily_key(user_id, "pnl")
        running_daily_pnl = float(self.cache.get(daily_pnl_key) or 0.0) + actual_pnl
        self.cache.set(daily_pnl_key, str(running_daily_pnl), ttl=self.settings.monitor_state_ttl_seconds)

        if actual_pnl < 0:
            self.cache.increment(self._daily_key(user_id, "losses"), ttl=self.settings.monitor_state_ttl_seconds)
            consecutive = self.cache.increment(f"micro:{user_id}:consecutive_losses", ttl=self.settings.monitor_state_ttl_seconds)
            if consecutive >= 2:
                self.cache.set(
                    f"micro:{user_id}:cooldown_until",
                    datetime.now(timezone.utc).isoformat(),
                    ttl=self.settings.cooldown_minutes * 60,
                )
        else:
            self.cache.set(f"micro:{user_id}:consecutive_losses", "0", ttl=self.settings.monitor_state_ttl_seconds)

        self.cache.set_json(
            f"micro:{user_id}:last_performance",
            {
                "alpha_realization_ratio": alpha_realization_ratio,
                "slippage_error": slippage_error,
                "execution_efficiency": execution_efficiency,
                "latency_ms": latency_ms,
                "running_daily_pnl": running_daily_pnl,
            },
            ttl=self.settings.monitor_state_ttl_seconds,
        )
        if actual_slippage_bps > self.settings.micro_slippage_threshold_bps:
            self.cache.set("micro:abnormal_slippage", "1", ttl=self.settings.monitor_state_ttl_seconds)
        return {
            "alpha_realization_ratio": alpha_realization_ratio,
            "slippage_error": slippage_error,
            "execution_efficiency": execution_efficiency,
            "running_daily_pnl": running_daily_pnl,
            "daily_loss_stop_triggered": running_daily_pnl <= -(account_equity * self.settings.micro_daily_loss_limit),
        }

    def compare_paper_vs_live(
        self,
        *,
        expected_paper_pnl: float,
        live_pnl: float,
        fees: float,
        slippage_cost: float,
        latency_ms: float,
    ) -> dict:
        deviation = expected_paper_pnl - live_pnl
        return {
            "paper_live_deviation": deviation,
            "fee_impact": fees,
            "slippage_impact": slippage_cost,
            "latency_impact": latency_ms / 1000,
            "adjust_execution": abs(deviation) > max(1.0, abs(expected_paper_pnl) * 0.25),
        }

    def _within_daily_trade_limit(self, user_id: str, account_equity: float) -> bool:
        trades = int(self.cache.get(self._daily_key(user_id, "trades")) or 0)
        limit = (
            self.settings.micro_max_trades_small_account
            if account_equity < self.settings.micro_single_trade_capital_threshold
            else self.settings.micro_max_trades_standard
        )
        return trades < limit

    def _cooldown_active(self, user_id: str) -> bool:
        return self.cache.get(f"micro:{user_id}:cooldown_until") is not None

    def _daily_loss_exceeded(self, user_id: str, account_equity: float) -> bool:
        daily_pnl = float(self.cache.get(self._daily_key(user_id, "pnl")) or 0.0)
        reference_equity = max(self.settings.exchange_min_notional, account_equity)
        return daily_pnl <= -(reference_equity * self.settings.micro_daily_loss_limit)

    def _abnormal_slippage(self, user_id: str) -> bool:
        return bool(self.cache.get("micro:abnormal_slippage"))

    def _daily_key(self, user_id: str, metric: str) -> str:
        return f"micro:{user_id}:{datetime.now(timezone.utc).date().isoformat()}:{metric}"

