from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.core.config import Settings
from app.schemas.monitoring import DrawdownStatus
from app.services.redis_cache import RedisCache


@dataclass
class UserProtectionControls:
    max_capital_allocation_pct: float
    daily_loss_limit: float
    emergency_stop_manual: bool
    emergency_stop_auto: bool
    emergency_stop_reason: str | None
    updated_at: datetime | None

    @property
    def emergency_stop_active(self) -> bool:
        return self.emergency_stop_manual or self.emergency_stop_auto


@dataclass
class DrawdownProtectionService:
    settings: Settings
    cache: RedisCache

    def _key(self, user_id: str) -> str:
        return f"drawdown:{user_id}"

    def _controls_key(self, user_id: str) -> str:
        return f"drawdown:controls:{user_id}"

    def _daily_key(self, user_id: str) -> str:
        return f"drawdown:daily:{user_id}"

    def load(self, user_id: str) -> DrawdownStatus:
        state = self.cache.get_json(self._key(user_id))
        if state:
            return DrawdownStatus(**state)
        return DrawdownStatus(
            current_equity=self.settings.default_portfolio_balance,
            peak_equity=self.settings.default_portfolio_balance,
            rolling_drawdown=0.0,
            state="NORMAL",
            cooldown_until=None,
        )

    def load_controls(self, user_id: str) -> UserProtectionControls:
        state = self.cache.get_json(self._controls_key(user_id))
        if state:
            updated_at = state.get("updated_at")
            return UserProtectionControls(
                max_capital_allocation_pct=float(state["max_capital_allocation_pct"]),
                daily_loss_limit=float(state["daily_loss_limit"]),
                emergency_stop_manual=bool(state.get("emergency_stop_manual", False)),
                emergency_stop_auto=bool(state.get("emergency_stop_auto", False)),
                emergency_stop_reason=state.get("emergency_stop_reason"),
                updated_at=datetime.fromisoformat(updated_at) if updated_at else None,
            )
        return UserProtectionControls(
            max_capital_allocation_pct=self.settings.user_max_capital_allocation_pct,
            daily_loss_limit=self.settings.daily_loss_limit,
            emergency_stop_manual=False,
            emergency_stop_auto=False,
            emergency_stop_reason=None,
            updated_at=None,
        )

    def update_controls(
        self,
        user_id: str,
        *,
        max_capital_allocation_pct: float | None = None,
        daily_loss_limit: float | None = None,
    ) -> UserProtectionControls:
        controls = self.load_controls(user_id)
        updated = UserProtectionControls(
            max_capital_allocation_pct=(
                max_capital_allocation_pct
                if max_capital_allocation_pct is not None
                else controls.max_capital_allocation_pct
            ),
            daily_loss_limit=(
                daily_loss_limit
                if daily_loss_limit is not None
                else controls.daily_loss_limit
            ),
            emergency_stop_manual=controls.emergency_stop_manual,
            emergency_stop_auto=controls.emergency_stop_auto,
            emergency_stop_reason=controls.emergency_stop_reason,
            updated_at=datetime.now(timezone.utc),
        )
        self._persist_controls(user_id, updated)
        return updated

    def activate_emergency_stop(self, user_id: str, *, reason: str, manual: bool = True) -> UserProtectionControls:
        controls = self.load_controls(user_id)
        updated = UserProtectionControls(
            max_capital_allocation_pct=controls.max_capital_allocation_pct,
            daily_loss_limit=controls.daily_loss_limit,
            emergency_stop_manual=manual or controls.emergency_stop_manual,
            emergency_stop_auto=(not manual) or controls.emergency_stop_auto,
            emergency_stop_reason=reason,
            updated_at=datetime.now(timezone.utc),
        )
        self._persist_controls(user_id, updated)
        return updated

    def clear_emergency_stop(self, user_id: str) -> UserProtectionControls:
        controls = self.load_controls(user_id)
        updated = UserProtectionControls(
            max_capital_allocation_pct=controls.max_capital_allocation_pct,
            daily_loss_limit=controls.daily_loss_limit,
            emergency_stop_manual=False,
            emergency_stop_auto=False,
            emergency_stop_reason=None,
            updated_at=datetime.now(timezone.utc),
        )
        self._persist_controls(user_id, updated)
        return updated

    def update(self, user_id: str, current_equity: float) -> DrawdownStatus:
        status = self.load(user_id)
        self._update_daily_tracker(user_id, current_equity)
        peak = max(status.peak_equity, current_equity)
        rolling_drawdown = max(0.0, (peak - current_equity) / max(peak, 1e-8))
        state = "NORMAL"
        cooldown_until = status.cooldown_until
        now = datetime.now(timezone.utc)
        if rolling_drawdown >= self.settings.pause_drawdown_limit:
            state = "PAUSED"
            cooldown_until = now + timedelta(minutes=self.settings.cooldown_minutes)
        elif cooldown_until and cooldown_until > now:
            state = "COOLDOWN"
        elif rolling_drawdown >= self.settings.rolling_drawdown_limit:
            state = "REDUCED"
            cooldown_until = now + timedelta(minutes=self.settings.cooldown_minutes)
        else:
            cooldown_until = None
        updated = DrawdownStatus(
            current_equity=current_equity,
            peak_equity=peak,
            rolling_drawdown=rolling_drawdown,
            state=state,
            cooldown_until=cooldown_until,
        )
        self.cache.set_json(
            self._key(user_id),
            updated.model_dump(mode="json"),
            ttl=self.settings.monitor_state_ttl_seconds,
        )
        self._enforce_daily_loss_limit(user_id, current_equity)
        return updated

    def capital_multiplier(self, user_id: str) -> float:
        status = self.load(user_id)
        controls = self.load_controls(user_id)
        if controls.emergency_stop_active:
            return 0.0
        if status.state in {"PAUSED", "COOLDOWN"}:
            return 0.0
        if status.state == "REDUCED":
            return self.settings.drawdown_reduction_factor
        return 1.0

    def daily_pnl_pct(self, user_id: str) -> float:
        state = self.cache.get_json(self._daily_key(user_id))
        if not state:
            return 0.0
        start_equity = float(state.get("start_equity", self.settings.default_portfolio_balance))
        current_equity = float(state.get("current_equity", start_equity))
        return (current_equity - start_equity) / max(start_equity, 1e-8)

    def _update_daily_tracker(self, user_id: str, current_equity: float) -> None:
        now = datetime.now(timezone.utc)
        current_day = now.date().isoformat()
        state = self.cache.get_json(self._daily_key(user_id)) or {}
        if state.get("date") != current_day:
            state = {
                "date": current_day,
                "start_equity": current_equity,
            }
        state["current_equity"] = current_equity
        self.cache.set_json(self._daily_key(user_id), state, ttl=self.settings.monitor_state_ttl_seconds)

    def _enforce_daily_loss_limit(self, user_id: str, current_equity: float) -> None:
        controls = self.load_controls(user_id)
        if controls.emergency_stop_manual or controls.emergency_stop_auto:
            return
        daily_pnl_pct = self.daily_pnl_pct(user_id)
        if daily_pnl_pct <= -controls.daily_loss_limit:
            self.activate_emergency_stop(
                user_id,
                reason=f"daily_loss_limit_exceeded:{daily_pnl_pct:.4f}",
                manual=False,
            )

    def _persist_controls(self, user_id: str, controls: UserProtectionControls) -> None:
        self.cache.set_json(
            self._controls_key(user_id),
            {
                "max_capital_allocation_pct": controls.max_capital_allocation_pct,
                "daily_loss_limit": controls.daily_loss_limit,
                "emergency_stop_manual": controls.emergency_stop_manual,
                "emergency_stop_auto": controls.emergency_stop_auto,
                "emergency_stop_reason": controls.emergency_stop_reason,
                "updated_at": controls.updated_at.isoformat() if controls.updated_at else None,
            },
            ttl=self.settings.monitor_state_ttl_seconds,
        )

