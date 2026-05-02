from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter

from engine.execution_engine import BrokerRejectedError, ExecutionEngine
from engine.meta_engine import MetaEngine
from engine.risk_engine import RiskEngine
from models.trade import SignalPayload, SignalResponse
from utils.logger import get_logger


@dataclass
class SignalRouterContext:
    meta_engine: MetaEngine
    risk_engine: RiskEngine
    execution_engine: ExecutionEngine
    strategies: list[str]


def create_signal_router(context: SignalRouterContext) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["signal"])
    logger = get_logger("signal-api")

    @router.post("/signal", response_model=SignalResponse)
    def receive_signal(signal: SignalPayload) -> SignalResponse:
        payload = SignalPayload(
            strategy=signal.strategy.strip().lower(),
            signal=signal.signal.strip().upper(),
            symbol=signal.symbol.strip().upper(),
            price=signal.price,
            atr=signal.atr,
            capital=signal.capital,
        )
        logger.info(
            "received signal strategy=%s signal=%s symbol=%s price=%s",
            payload.strategy,
            payload.signal,
            payload.symbol,
            payload.price,
        )

        meta = context.meta_engine.evaluate_signal(payload, context.strategies)
        if not meta.approved:
            trade = context.execution_engine.log_rejection(
                payload,
                meta_approved=False,
                risk_approved=False,
                rejection_reason=meta.reason,
                confidence=meta.confidence,
            )
            logger.info("signal rejected by meta engine trade_id=%s", trade.trade_id)
            return SignalResponse(
                status="rejected",
                executed=False,
                selected_strategy=meta.selected_strategy,
                confidence=meta.confidence,
                meta=meta,
                trade=trade,
            )

        risk = context.risk_engine.evaluate_signal(payload)
        if not risk.approved:
            trade = context.execution_engine.log_rejection(
                payload,
                meta_approved=True,
                risk_approved=False,
                rejection_reason=risk.reason,
                stop_loss=risk.stop_loss,
                take_profit=risk.take_profit,
                atr=risk.atr,
                confidence=meta.confidence,
            )
            logger.info("signal rejected by risk engine trade_id=%s", trade.trade_id)
            return SignalResponse(
                status="rejected",
                executed=False,
                selected_strategy=meta.selected_strategy,
                confidence=meta.confidence,
                meta=meta,
                risk=risk,
                trade=trade,
            )

        execution_rejection = context.execution_engine.execution_rejection_reason(payload, meta, risk)
        if execution_rejection is not None:
            trade = context.execution_engine.log_rejection(
                payload,
                meta_approved=True,
                risk_approved=True,
                rejection_reason=execution_rejection,
                stop_loss=risk.stop_loss,
                take_profit=risk.take_profit,
                atr=risk.atr,
                confidence=meta.confidence,
            )
            logger.info("signal rejected by execution engine trade_id=%s", trade.trade_id)
            return SignalResponse(
                status="rejected",
                executed=False,
                selected_strategy=meta.selected_strategy,
                confidence=meta.confidence,
                meta=meta,
                risk=risk,
                trade=trade,
            )

        try:
            execution = context.execution_engine.execute(payload, meta, risk)
        except BrokerRejectedError as exc:
            trade = context.execution_engine.log_rejection(
                payload,
                meta_approved=True,
                risk_approved=True,
                rejection_reason=exc.reason,
                stop_loss=risk.stop_loss,
                take_profit=risk.take_profit,
                atr=risk.atr,
                confidence=meta.confidence,
                broker_order_id=exc.broker_order_id,
                exchange_status=exc.exchange_status,
            )
            logger.info("signal rejected by broker trade_id=%s", trade.trade_id)
            return SignalResponse(
                status="rejected",
                executed=False,
                selected_strategy=meta.selected_strategy,
                confidence=meta.confidence,
                meta=meta,
                risk=risk,
                trade=trade,
            )
        logger.info("signal executed trade_id=%s", execution.trade.trade_id)
        return SignalResponse(
            status="executed",
            executed=True,
            selected_strategy=meta.selected_strategy,
            confidence=meta.confidence,
            meta=meta,
            risk=risk,
            execution=execution,
            trade=execution.trade,
        )

    return router
