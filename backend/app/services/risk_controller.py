from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.config import Settings
from app.schemas.monitoring import RolloutStatus
from app.services.drawdown_protection import DrawdownProtectionService
from app.services.redis_cache import RedisCache
from app.services.signal_broadcaster import SignalBroadcaster


@dataclass(frozen=True)
class RiskProfile:
    level: str
    confidence_floor: float
    daily_loss_limit: float
    risk_fraction: float
    max_active_trades: int
    allowed_symbols: list[str]
    subscription_risk_profile: str
    allow_counter_trend: bool
    allow_high_volatility: bool


@dataclass
class RiskController:
    settings: Settings
    cache: RedisCache
    drawdown_protection: DrawdownProtectionService
    signal_broadcaster: SignalBroadcaster | None = None

    def _key(self, user_id: str) -> str:
        return f"risk:profile:{user_id}"

    def profile(self, user_id: str) -> RiskProfile:
        payload = self.cache.get_json(self._key(user_id)) or {}
        level = str(payload.get("level", "medium") or "medium").lower()
        return self._profile_for_level(level)

    def set_profile(self, user_id: str, level: str) -> RiskProfile:
        profile = self._profile_for_level(level)
        self.cache.set_json(
            self._key(user_id),
            {
                "level": profile.level,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            ttl=self.settings.monitor_state_ttl_seconds,
        )
        self.drawdown_protection.update_controls(
            user_id,
            daily_loss_limit=profile.daily_loss_limit,
        )
        if self.signal_broadcaster is not None:
            existing = self.cache.get_json(f"subscription:{user_id}") or {}
            self.signal_broadcaster.register_subscription(
                user_id=user_id,
                tier=str(existing.get("tier", "vip") or "vip"),
                balance=float(existing.get("balance", self.settings.default_portfolio_balance) or self.settings.default_portfolio_balance),
                risk_profile=profile.subscription_risk_profile,
            )
        if self.settings.trading_mode == "paper":
            self.cache.set_json(
                "rollout:status",
                RolloutStatus(
                    stage_index=2,
                    stage_name="LIMITED",
                    capital_fraction=float(self.settings.local_paper_active_rollout_fraction),
                    mode="paper",
                    eligible_for_upgrade=False,
                    downgrade_flag=False,
                ).model_dump(),
                ttl=self.settings.monitor_state_ttl_seconds,
            )
        return profile

    def _profile_for_level(self, level: str) -> RiskProfile:
        normalized = str(level or "medium").lower()
        if normalized == "low":
            return RiskProfile(
                level="low",
                confidence_floor=float(self.settings.risk_profile_low_confidence_floor),
                daily_loss_limit=float(self.settings.risk_profile_low_daily_loss_limit),
                risk_fraction=float(self.settings.risk_profile_low_risk_fraction),
                max_active_trades=int(self.settings.risk_profile_low_max_active_trades),
                allowed_symbols=[str(symbol).upper() for symbol in self.settings.risk_profile_low_allowed_symbols],
                subscription_risk_profile="conservative",
                allow_counter_trend=False,
                allow_high_volatility=False,
            )
        if normalized == "high":
            return RiskProfile(
                level="high",
                confidence_floor=float(self.settings.risk_profile_high_confidence_floor),
                daily_loss_limit=float(self.settings.risk_profile_high_daily_loss_limit),
                risk_fraction=float(self.settings.risk_profile_high_risk_fraction),
                max_active_trades=int(self.settings.risk_profile_high_max_active_trades),
                allowed_symbols=[str(symbol).upper() for symbol in self.settings.risk_profile_high_allowed_symbols],
                subscription_risk_profile="aggressive",
                allow_counter_trend=True,
                allow_high_volatility=True,
            )
        return RiskProfile(
            level="medium",
            confidence_floor=float(self.settings.risk_profile_medium_confidence_floor),
            daily_loss_limit=float(self.settings.risk_profile_medium_daily_loss_limit),
            risk_fraction=float(self.settings.risk_profile_medium_risk_fraction),
            max_active_trades=int(self.settings.risk_profile_medium_max_active_trades),
            allowed_symbols=[str(symbol).upper() for symbol in self.settings.risk_profile_medium_allowed_symbols],
            subscription_risk_profile="moderate",
            allow_counter_trend=False,
            allow_high_volatility=True,
        )
