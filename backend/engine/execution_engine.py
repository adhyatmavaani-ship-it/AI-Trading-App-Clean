from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from backend.db.database import SQLiteTradeDatabase
from backend.models.trade import ExecutionResult, MetaDecision, RiskDecision, SignalPayload, TradeRecord
from backend.services.broker_adapter import BrokerAdapter


class BrokerRejectedError(RuntimeError):
    def __init__(
        self,
        *,
        reason: str,
        exchange_status: str | None = None,
        broker_order_id: str | None = None,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.exchange_status = exchange_status
        self.broker_order_id = broker_order_id


class ExecutionEngine:
    def __init__(
        self,
        db: SQLiteTradeDatabase,
        broker: BrokerAdapter,
        *,
        account_equity: float,
        risk_per_trade_pct: float = 0.02,
        min_confidence: float = 0.3,
        cooldown_minutes: int = 15,
        max_open_trades: int = 2,
        dry_run: bool = False,
        kill_switch: bool = False,
        max_total_exposure_pct: float = 3.0,
    ) -> None:
        self._db = db
        self._broker = broker
        self._account_equity = account_equity
        self._risk_per_trade_pct = risk_per_trade_pct
        self._min_confidence = min_confidence
        self._cooldown_window = timedelta(minutes=cooldown_minutes)
        self._max_open_trades = max_open_trades
        self._dry_run = bool(dry_run)
        self._kill_switch = bool(kill_switch)
        self._max_total_exposure_pct = max(float(max_total_exposure_pct), 0.0)

    def can_trade(
        self,
        signal: SignalPayload | None = None,
        risk: RiskDecision | None = None,
        *,
        now: datetime | None = None,
    ) -> tuple[bool, str | None]:
        current_time = now or datetime.now(timezone.utc)
        if self._kill_switch:
            return False, "broker_kill_switch_active"

        last_trade_time = self._db.latest_executed_trade_time()
        if last_trade_time is not None and current_time - last_trade_time < self._cooldown_window:
            return False, "cooldown_active"

        if self._db.open_trade_count() >= self._max_open_trades:
            return False, "max_open_trades_reached"

        if signal is not None and risk is not None:
            capital = float(signal.capital or self._account_equity)
            sl_distance = abs(signal.price - risk.stop_loss)
            position_size = self.calculate_position_size(capital, sl_distance)
            projected_exposure = self._db.open_exposure() + abs(signal.price * position_size)
            exposure_limit = self._account_equity * self._max_total_exposure_pct
            if exposure_limit > 0 and projected_exposure > exposure_limit:
                return False, "max_exposure_reached"

        return True, None

    def execution_rejection_reason(
        self,
        signal: SignalPayload,
        meta: MetaDecision,
        risk: RiskDecision,
    ) -> str | None:
        if meta.confidence < self._min_confidence:
            return "low_confidence"
        allowed, reason = self.can_trade(signal, risk)
        if not allowed:
            return reason
        return None

    def calculate_position_size(self, capital: float, sl_distance: float) -> float:
        risk_amount = capital * self._risk_per_trade_pct
        return 0.0 if sl_distance <= 0 else risk_amount / sl_distance

    def _place_order(
        self,
        signal: SignalPayload,
        *,
        quantity: float,
        stop_loss: float,
        take_profit: float,
    ) -> dict[str, object]:
        if self._dry_run and getattr(self._broker, "is_live", False):
            return {
                "status": "filled",
                "exchange_status": "dry_run",
                "exchange": getattr(self._broker, "name", "broker"),
                "broker_order_id": f"dryrun-{uuid4().hex[:12]}",
                "symbol": signal.symbol,
                "side": signal.signal,
                "qty": float(quantity),
                "sl": float(stop_loss),
                "tp": float(take_profit),
            }
        return self._broker.place_order(
            symbol=signal.symbol,
            side=signal.signal,
            quantity=quantity,
            sl=stop_loss,
            tp=take_profit,
        )

    def execute(
        self,
        signal: SignalPayload,
        meta: MetaDecision,
        risk: RiskDecision,
    ) -> ExecutionResult:
        if not meta.approved:
            raise ValueError("meta approval required before execution")
        if not risk.approved:
            raise ValueError("risk approval required before execution")
        execution_rejection = self.execution_rejection_reason(signal, meta, risk)
        if execution_rejection is not None:
            raise ValueError(f"execution rejected: {execution_rejection}")

        capital = float(signal.capital or self._account_equity)
        sl_distance = abs(signal.price - risk.stop_loss)
        position_size = self.calculate_position_size(capital, sl_distance)
        broker_order = self._place_order(
            signal,
            quantity=position_size,
            stop_loss=risk.stop_loss,
            take_profit=risk.take_profit,
        )
        broker_status = str(broker_order.get("status", "")).strip().lower()
        exchange_status = str(
            broker_order.get("exchange_status") or broker_order.get("status") or "unknown"
        ).strip().lower()
        broker_order_id = broker_order.get("broker_order_id")
        if broker_status != "filled":
            raise BrokerRejectedError(
                reason="broker_reject",
                exchange_status=exchange_status,
                broker_order_id=str(broker_order_id) if broker_order_id else None,
            )

        trade = TradeRecord(
            strategy=signal.strategy,
            signal=signal.signal,
            symbol=signal.symbol,
            entry_price=signal.price,
            stop_loss=risk.stop_loss,
            take_profit=risk.take_profit,
            position_size=position_size,
            atr=risk.atr,
            confidence=meta.confidence,
            approved_by_meta=True,
            approved_by_risk=True,
            status="open",
            broker_order_id=str(broker_order_id) if broker_order_id else None,
            exchange_status=exchange_status,
            filled_qty=position_size,
            avg_fill_price=signal.price,
        )
        self._db.log_trade(trade)
        return ExecutionResult(
            status="executed",
            message=f"trade executed via {getattr(self._broker, 'name', 'broker')} broker",
            trade=trade,
        )

    def log_rejection(
        self,
        signal: SignalPayload,
        *,
        meta_approved: bool,
        risk_approved: bool,
        rejection_reason: str,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        atr: float | None = None,
        confidence: float | None = None,
        broker_order_id: str | None = None,
        exchange_status: str | None = None,
    ) -> TradeRecord:
        trade = TradeRecord(
            strategy=signal.strategy,
            signal=signal.signal,
            symbol=signal.symbol,
            entry_price=signal.price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            atr=atr,
            confidence=confidence,
            approved_by_meta=meta_approved,
            approved_by_risk=risk_approved,
            status="rejected",
            rejection_reason=rejection_reason,
            broker_order_id=broker_order_id,
            exchange_status=exchange_status,
        )
        self._db.log_trade(trade)
        return trade
