from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone

from app.core.config import Settings


@dataclass(frozen=True)
class RiskShieldBracket:
    entry_price: float
    stop_loss: float
    take_profit: float


@dataclass(frozen=True)
class UserRiskState:
    account_balance: float
    daily_realized_pnl: float = 0.0
    consecutive_losses: int = 0
    closed_trades: int = 0
    winning_trades: int = 0
    average_risk_reward: float = 0.0


@dataclass(frozen=True)
class RiskShieldDecision:
    approved: bool
    reason: str
    reason_code: str
    auto_quantity: float = 0.0
    max_notional: float = 0.0
    risk_amount: float = 0.0
    risk_per_unit: float = 0.0
    risk_reward: float = 0.0
    daily_loss_pct: float = 0.0
    locked_until: str | None = None
    license_status: str = "Learning Mode"
    live_unlocked: bool = False
    details: dict[str, float | str | bool] = field(default_factory=dict)


class RiskShieldService:
    """Strict pre-execution guard for paper/live order requests."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def evaluate_order(
        self,
        *,
        side: str,
        requested_notional: float,
        bracket: RiskShieldBracket,
        user_state: UserRiskState,
        now: datetime | None = None,
    ) -> RiskShieldDecision:
        current_time = now or datetime.now(timezone.utc)
        account_balance = max(float(user_state.account_balance), 0.0)
        risk_amount = account_balance * float(self.settings.base_risk_per_trade)
        daily_loss_pct = self._daily_loss_pct(user_state)
        license_status, live_unlocked = self.rookie_license_status(user_state)

        daily_loss_limit = float(self.settings.daily_loss_limit)
        if user_state.daily_realized_pnl <= -(account_balance * daily_loss_limit):
            return self._blocked(
                reason="Daily loss circuit breaker active until midnight.",
                reason_code="DAILY_LOSS_LIMIT_REACHED",
                locked_until=self._next_midnight(current_time),
                daily_loss_pct=daily_loss_pct,
                license_status=license_status,
                live_unlocked=live_unlocked,
            )

        if int(user_state.consecutive_losses) >= int(self.settings.max_consecutive_losses):
            return self._blocked(
                reason="Consecutive loss lock active for 2 hours.",
                reason_code="CONSECUTIVE_LOSS_LOCK",
                locked_until=current_time + timedelta(hours=2),
                daily_loss_pct=daily_loss_pct,
                license_status=license_status,
                live_unlocked=live_unlocked,
            )

        entry = float(bracket.entry_price)
        stop = float(bracket.stop_loss)
        target = float(bracket.take_profit)
        if entry <= 0 or stop <= 0 or target <= 0:
            return self._blocked(
                reason="Entry, stop-loss, and target are mandatory before execution.",
                reason_code="MANDATORY_BRACKET_MISSING",
                daily_loss_pct=daily_loss_pct,
                license_status=license_status,
                live_unlocked=live_unlocked,
            )

        normalized_side = side.upper()
        if normalized_side == "BUY":
            risk_per_unit = entry - stop
            reward_per_unit = target - entry
        else:
            risk_per_unit = stop - entry
            reward_per_unit = entry - target
        if risk_per_unit <= 0 or reward_per_unit <= 0:
            return self._blocked(
                reason="Stop-loss and target must be on the protective side of the entry.",
                reason_code="INVALID_BRACKET_DIRECTION",
                daily_loss_pct=daily_loss_pct,
                license_status=license_status,
                live_unlocked=live_unlocked,
            )

        risk_reward = reward_per_unit / risk_per_unit
        min_rr = float(self.settings.strict_trade_min_take_profit_rr)
        if risk_reward < min_rr:
            return self._blocked(
                reason=f"Risk-reward must be at least 1:{min_rr:.1f}.",
                reason_code="RISK_REWARD_TOO_LOW",
                daily_loss_pct=daily_loss_pct,
                risk_per_unit=risk_per_unit,
                risk_reward=risk_reward,
                license_status=license_status,
                live_unlocked=live_unlocked,
            )

        auto_quantity = risk_amount / risk_per_unit
        max_notional = auto_quantity * entry
        if requested_notional > max_notional * 1.000001:
            return self._blocked(
                reason="Requested size is above the automatic risk limit.",
                reason_code="POSITION_SIZE_EXCEEDS_RISK_LIMIT",
                daily_loss_pct=daily_loss_pct,
                risk_amount=risk_amount,
                risk_per_unit=risk_per_unit,
                risk_reward=risk_reward,
                auto_quantity=auto_quantity,
                max_notional=max_notional,
                license_status=license_status,
                live_unlocked=live_unlocked,
            )

        return RiskShieldDecision(
            approved=True,
            reason="Risk shield approved. Bracket, sizing, and circuit breakers are valid.",
            reason_code="APPROVED",
            auto_quantity=round(auto_quantity, 8),
            max_notional=round(max_notional, 8),
            risk_amount=round(risk_amount, 8),
            risk_per_unit=round(risk_per_unit, 8),
            risk_reward=round(risk_reward, 8),
            daily_loss_pct=round(daily_loss_pct, 8),
            license_status=license_status,
            live_unlocked=live_unlocked,
            details={
                "max_risk_per_trade_pct": float(self.settings.base_risk_per_trade),
                "daily_loss_limit_pct": float(self.settings.daily_loss_limit),
                "max_consecutive_losses": int(self.settings.max_consecutive_losses),
            },
        )

    def rookie_license_status(self, state: UserRiskState) -> tuple[str, bool]:
        closed = int(state.closed_trades)
        wins = int(state.winning_trades)
        win_rate = wins / max(closed, 1)
        avg_rr = float(state.average_risk_reward)
        unlocked = closed >= 10 and win_rate > 0.45 and avg_rr >= 1.5
        return ("Live Trade Ready" if unlocked else "Learning Mode", unlocked)

    def _blocked(
        self,
        *,
        reason: str,
        reason_code: str,
        daily_loss_pct: float,
        locked_until: datetime | None = None,
        risk_amount: float = 0.0,
        risk_per_unit: float = 0.0,
        risk_reward: float = 0.0,
        auto_quantity: float = 0.0,
        max_notional: float = 0.0,
        license_status: str,
        live_unlocked: bool,
    ) -> RiskShieldDecision:
        return RiskShieldDecision(
            approved=False,
            reason=reason,
            reason_code=reason_code,
            auto_quantity=round(auto_quantity, 8),
            max_notional=round(max_notional, 8),
            risk_amount=round(risk_amount, 8),
            risk_per_unit=round(risk_per_unit, 8),
            risk_reward=round(risk_reward, 8),
            daily_loss_pct=round(daily_loss_pct, 8),
            locked_until=locked_until.isoformat() if locked_until else None,
            license_status=license_status,
            live_unlocked=live_unlocked,
        )

    def _daily_loss_pct(self, state: UserRiskState) -> float:
        balance = max(float(state.account_balance), 1e-8)
        loss = min(0.0, float(state.daily_realized_pnl))
        return abs(loss) / balance

    def _next_midnight(self, now: datetime) -> datetime:
        local_now = now.astimezone(timezone.utc)
        tomorrow = local_now.date() + timedelta(days=1)
        return datetime.combine(tomorrow, time.min, tzinfo=timezone.utc)
