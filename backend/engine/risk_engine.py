from __future__ import annotations

from db.database import SQLiteTradeDatabase
from models.trade import RiskDecision, SignalPayload


class RiskEngine:
    def __init__(
        self,
        db: SQLiteTradeDatabase,
        *,
        account_equity: float,
        max_risk_per_trade_pct: float = 0.02,
        max_daily_loss_pct: float = 0.03,
        max_consecutive_losses: int = 3,
        stop_loss_pct: float = 0.01,
        take_profit_pct: float = 0.02,
        stop_loss_atr_multiplier: float = 1.5,
        take_profit_atr_multiplier: float = 3.0,
    ) -> None:
        self._db = db
        self._account_equity = account_equity
        self._max_risk_per_trade_pct = max_risk_per_trade_pct
        self._max_daily_loss_pct = max_daily_loss_pct
        self._max_consecutive_losses = max_consecutive_losses
        self._stop_loss_pct = stop_loss_pct
        self._take_profit_pct = take_profit_pct
        self._stop_loss_atr_multiplier = stop_loss_atr_multiplier
        self._take_profit_atr_multiplier = take_profit_atr_multiplier

    def evaluate_signal(self, signal: SignalPayload) -> RiskDecision:
        atr = self._resolve_atr(signal)
        stop_loss, take_profit = self._protective_levels(signal, atr)
        risk_pct = abs(signal.price - stop_loss) / signal.price
        daily_pnl = self._db.daily_pnl()
        consecutive_losses = self._db.consecutive_losses()
        capital = float(signal.capital or self._account_equity)
        max_daily_loss_amount = capital * self._max_daily_loss_pct

        if consecutive_losses >= self._max_consecutive_losses:
            return RiskDecision(
                approved=False,
                reason="max_consecutive_losses_reached",
                risk_pct=risk_pct,
                stop_loss=stop_loss,
                take_profit=take_profit,
                atr=atr,
                daily_pnl=daily_pnl,
                consecutive_losses=consecutive_losses,
            )

        if daily_pnl <= -max_daily_loss_amount:
            return RiskDecision(
                approved=False,
                reason="max_daily_loss_reached",
                risk_pct=risk_pct,
                stop_loss=stop_loss,
                take_profit=take_profit,
                atr=atr,
                daily_pnl=daily_pnl,
                consecutive_losses=consecutive_losses,
            )

        if risk_pct > self._max_risk_per_trade_pct:
            return RiskDecision(
                approved=False,
                reason="risk_per_trade_limit_exceeded",
                risk_pct=risk_pct,
                stop_loss=stop_loss,
                take_profit=take_profit,
                atr=atr,
                daily_pnl=daily_pnl,
                consecutive_losses=consecutive_losses,
            )

        return RiskDecision(
            approved=True,
            reason="risk_validated",
            risk_pct=risk_pct,
            stop_loss=stop_loss,
            take_profit=take_profit,
            atr=atr,
            daily_pnl=daily_pnl,
            consecutive_losses=consecutive_losses,
        )

    def _resolve_atr(self, signal: SignalPayload) -> float:
        if signal.atr is not None and signal.atr > 0:
            return float(signal.atr)
        # Derive a synthetic ATR that preserves the existing stop/take-profit shape.
        return float(signal.price) * self._stop_loss_pct / max(self._stop_loss_atr_multiplier, 1e-8)

    def _protective_levels(self, signal: SignalPayload, atr: float) -> tuple[float, float]:
        stop_distance = atr * self._stop_loss_atr_multiplier
        take_profit_distance = atr * self._take_profit_atr_multiplier
        if signal.signal == "BUY":
            stop_loss = signal.price - stop_distance
            take_profit = signal.price + take_profit_distance
        else:
            stop_loss = signal.price + stop_distance
            take_profit = signal.price - take_profit_distance
        return stop_loss, take_profit
