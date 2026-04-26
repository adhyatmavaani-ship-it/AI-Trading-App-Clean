from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.schemas.monitoring import RolloutStatus
from app.services.redis_cache import RedisCache


@dataclass
class RolloutManager:
    settings: Settings
    cache: RedisCache

    STAGE_NAMES = ("SHADOW", "MICRO", "LIMITED", "EXPANDED")

    def is_micro_stage(self) -> bool:
        return self.status().stage_name == "MICRO"

    def effective_capital_fraction(self, account_equity: float) -> float:
        status = self.status()
        if account_equity <= self.settings.micro_max_capital_threshold:
            return min(status.capital_fraction if status.capital_fraction > 0 else 0.01, 0.10)
        return status.capital_fraction

    def status(self) -> RolloutStatus:
        payload = self.cache.get_json("rollout:status")
        if payload:
            return RolloutStatus(**payload)
        stage_index = 0 if self.settings.trading_mode == "paper" else min(3, len(self.settings.rollout_stages) - 1)
        status = RolloutStatus(
            stage_index=stage_index,
            stage_name=self.STAGE_NAMES[stage_index],
            capital_fraction=self.settings.rollout_stages[stage_index],
            mode=self.settings.trading_mode,
            eligible_for_upgrade=False,
            downgrade_flag=False,
        )
        self.cache.set_json("rollout:status", status.model_dump(), ttl=self.settings.monitor_state_ttl_seconds)
        return status

    def record_performance(self, win_rate: float, profit_factor: float, trades: int, drawdown: float = 0.0) -> RolloutStatus:
        current = self.status()
        eligible = (
            trades >= self.settings.rollout_min_trades
            and win_rate >= self.settings.rollout_win_rate_threshold
            and profit_factor >= self.settings.rollout_profit_factor_threshold
        )
        stage_index = current.stage_index
        downgrade_flag = False
        if drawdown >= self.settings.pause_drawdown_limit and stage_index > 0:
            stage_index -= 1
            downgrade_flag = True
        if eligible and stage_index < len(self.settings.rollout_stages) - 1:
            stage_index += 1
        updated = RolloutStatus(
            stage_index=stage_index,
            stage_name=self.STAGE_NAMES[stage_index],
            capital_fraction=self.settings.rollout_stages[stage_index],
            mode="live" if stage_index >= 2 and self.settings.trading_mode == "live" else "paper",
            eligible_for_upgrade=eligible,
            downgrade_flag=downgrade_flag,
        )
        self.cache.set_json("rollout:status", updated.model_dump(), ttl=self.settings.monitor_state_ttl_seconds)
        return updated
