from __future__ import annotations

from dataclasses import dataclass
import math
import time
import uuid

from app.core.config import Settings
from app.schemas.risk_coach import (
    HeatmapZone,
    PanicCloseRequest,
    PostMortemInsight,
    PostMortemResponse,
    RiskEvaluationRequest,
    RiskEvaluationResponse,
    TradeCloseRequest,
    TradeCreateRequest,
    TradePatchRequest,
    TradeSnapshot,
)
from app.services.risk_coach_market import RiskCoachMarketService


@dataclass(slots=True)
class TradeRecord:
    snapshot: TradeSnapshot
    account_equity: float
    fee_bps: float
    slippage_bps: float
    confidence: float
    liquidity_score: float
    freshness_seconds: int


class RiskCoachService:
    def __init__(self, settings: Settings, market_service: RiskCoachMarketService) -> None:
        self.settings = settings
        self.market_service = market_service
        self._trades: dict[str, TradeRecord] = {}

    def evaluate(self, request: RiskEvaluationRequest) -> RiskEvaluationResponse:
        fee_bps = float(request.taker_fee_bps if request.taker_fee_bps is not None else self.settings.taker_fee_bps)
        slippage_bps = float(request.slippage_bps if request.slippage_bps is not None else self.settings.slippage_bps)
        risk_per_unit = abs(request.entry - request.stop_loss)
        fee_per_unit = request.entry * (fee_bps / 10_000.0) * 2.0
        slippage_per_unit = request.entry * (slippage_bps / 10_000.0) * 2.0
        effective_risk_per_unit = risk_per_unit + fee_per_unit + slippage_per_unit
        position_size = 0.0 if effective_risk_per_unit <= 0 else request.risk_amount / effective_risk_per_unit
        notional = position_size * request.entry
        leveraged_notional = notional * request.leverage
        risk_pct = request.risk_amount / request.account_equity
        reward = abs(request.take_profit - request.entry)
        effective_reward = max(reward - fee_per_unit - slippage_per_unit, 0.0)
        effective_rr = 0.0 if effective_risk_per_unit <= 0 else effective_reward / effective_risk_per_unit
        expected_value = (request.confidence * effective_rr) - (1.0 - request.confidence)
        heatmap = self._heatmap_intensity(
            p_win=request.confidence,
            reliability=request.reliability,
            freshness_seconds=request.freshness_seconds,
            liquidity_score=request.liquidity_score,
            expected_value=expected_value,
        )
        blockers: list[str] = []
        warnings: list[str] = []
        if risk_pct > 0.03:
            blockers.append("Risk exceeds 3% of account equity.")
        if effective_rr < 1.2:
            blockers.append("Effective risk/reward is below the 1.2 minimum.")
        if leveraged_notional > request.account_equity * max(request.leverage, 1.0):
            warnings.append("Leverage magnifies notional exposure beyond spot-equivalent size.")
        if request.side == "long" and request.stop_loss >= request.entry:
            blockers.append("Long trades require stop-loss below entry.")
        if request.side == "short" and request.stop_loss <= request.entry:
            blockers.append("Short trades require stop-loss above entry.")
        if request.side == "long" and request.take_profit <= request.entry:
            blockers.append("Long trades require take-profit above entry.")
        if request.side == "short" and request.take_profit >= request.entry:
            blockers.append("Short trades require take-profit below entry.")
        if heatmap.state != "glow":
            warnings.append("Heatmap is muted because freshness, reliability, or EV is weak.")
        return RiskEvaluationResponse(
            allowed=not blockers,
            blockers=blockers,
            warnings=warnings,
            position_size=round(position_size, 8),
            quantity_step=round(position_size, 8),
            gross_risk_per_unit=round(risk_per_unit, 8),
            effective_risk_per_unit=round(effective_risk_per_unit, 8),
            fee_per_unit=round(fee_per_unit, 8),
            slippage_per_unit=round(slippage_per_unit, 8),
            risk_pct_of_equity=round(risk_pct, 6),
            notional=round(notional, 8),
            leveraged_notional=round(leveraged_notional, 8),
            effective_rr=round(effective_rr, 6),
            expected_value=round(expected_value, 6),
            heatmap_intensity=round(heatmap.intensity, 6),
            heatmap_state=heatmap.state,
        )

    def build_heatmap(self, request: RiskEvaluationRequest) -> HeatmapZone:
        evaluation = self.evaluate(request)
        lower = min(request.entry, request.stop_loss)
        upper = max(request.entry, request.take_profit)
        return HeatmapZone(
            start_price=round(lower, 8),
            end_price=round(upper, 8),
            intensity=evaluation.heatmap_intensity,
            state=evaluation.heatmap_state,  # type: ignore[arg-type]
            expected_value=evaluation.expected_value,
            reliability=request.reliability,
            freshness_seconds=request.freshness_seconds,
            liquidity_score=request.liquidity_score,
        )

    def create_trade(self, request: TradeCreateRequest) -> TradeSnapshot:
        evaluation = self.evaluate(
            RiskEvaluationRequest(
                symbol=request.symbol,
                side=request.side,
                account_equity=request.account_equity,
                risk_amount=request.risk_amount,
                entry=request.entry,
                stop_loss=request.stop_loss,
                take_profit=request.take_profit,
                leverage=request.leverage,
                maker_fee_bps=request.maker_fee_bps,
                taker_fee_bps=request.taker_fee_bps,
                slippage_bps=request.slippage_bps,
                confidence=request.p_win,
                reliability=request.reliability,
                liquidity_score=request.liquidity_score,
                freshness_seconds=request.freshness_seconds,
            )
        )
        trade = TradeSnapshot(
            trade_id=uuid.uuid4().hex,
            symbol=request.symbol.upper(),
            side=request.side,
            state="confirmed" if evaluation.allowed else "failed",
            entry=request.entry,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            p_win=request.p_win,
            reliability=request.reliability,
            rr=evaluation.effective_rr,
            leverage=request.leverage,
            risk_amount=request.risk_amount,
            position_size=evaluation.position_size,
            created_at=int(time.time()),
        )
        self._trades[trade.trade_id] = TradeRecord(
            snapshot=trade,
            account_equity=request.account_equity,
            fee_bps=float(request.taker_fee_bps if request.taker_fee_bps is not None else self.settings.taker_fee_bps),
            slippage_bps=float(request.slippage_bps if request.slippage_bps is not None else self.settings.slippage_bps),
            confidence=request.confidence,
            liquidity_score=request.liquidity_score,
            freshness_seconds=request.freshness_seconds,
        )
        return trade

    def patch_trade(self, trade_id: str, request: TradePatchRequest) -> TradeSnapshot:
        record = self._trades[trade_id]
        snapshot = record.snapshot.model_copy(
            update={
                "entry": request.entry if request.entry is not None else record.snapshot.entry,
                "stop_loss": request.stop_loss if request.stop_loss is not None else record.snapshot.stop_loss,
                "take_profit": request.take_profit if request.take_profit is not None else record.snapshot.take_profit,
                "state": "pending",
            }
        )
        record.snapshot = snapshot.model_copy(update={"state": "confirmed"})
        self._trades[trade_id] = record
        return record.snapshot

    def close_trade(self, trade_id: str, request: TradeCloseRequest) -> PostMortemResponse:
        record = self._trades[trade_id]
        snapshot = record.snapshot.model_copy(
            update={
                "state": "closed",
                "closed_at": int(time.time()),
                "close_price": request.exit_price,
            }
        )
        record.snapshot = snapshot
        prices = self.market_service.snapshot_prices_since(snapshot.created_at)
        if not prices:
            prices = [snapshot.entry, request.exit_price]
        risk_distance = abs(snapshot.entry - snapshot.stop_loss) or 1e-8
        if snapshot.side == "long":
            mfe = max(prices) - snapshot.entry
            mae = snapshot.entry - min(prices)
            realized = request.exit_price - snapshot.entry
        else:
            mfe = snapshot.entry - min(prices)
            mae = max(prices) - snapshot.entry
            realized = snapshot.entry - request.exit_price
        response = PostMortemResponse(
            trade=snapshot,
            mfe=round(mfe, 8),
            mae=round(mae, 8),
            mfe_r=round(mfe / risk_distance, 6),
            mae_r=round(mae / risk_distance, 6),
            realized_rr=round(realized / risk_distance, 6),
            insights=self._build_insights(snapshot, mfe, mae, realized, risk_distance),
        )
        return response

    def panic_close(self, request: PanicCloseRequest) -> dict[str, object]:
        results: list[dict[str, object]] = []
        ids = request.trade_ids or list(self._trades.keys())
        for trade_id in ids:
            record = self._trades.get(trade_id)
            if record is None or record.snapshot.state == "closed":
                results.append({"trade_id": trade_id, "status": "skipped"})
                continue
            latest = self.market_service.latest_close() or record.snapshot.entry
            post_mortem = self.close_trade(trade_id, TradeCloseRequest(exit_price=latest))
            results.append(
                {
                    "trade_id": trade_id,
                    "status": "closed",
                    "close_price": latest,
                    "realized_rr": post_mortem.realized_rr,
                }
            )
        return {
            "results": results,
            "recap": {
                "closed": sum(1 for item in results if item["status"] == "closed"),
                "skipped": sum(1 for item in results if item["status"] == "skipped"),
            },
            "educational_only": "Educational only. Not financial advice. No guaranteed profits.",
        }

    def list_trades(self) -> list[TradeSnapshot]:
        return [record.snapshot for record in self._trades.values()]

    def _heatmap_intensity(
        self,
        *,
        p_win: float,
        reliability: float,
        freshness_seconds: int,
        liquidity_score: float,
        expected_value: float,
    ) -> HeatmapZone:
        freshness = max(0.0, min(1.0, 1.0 - (freshness_seconds / 300.0)))
        intensity = p_win * reliability * freshness * liquidity_score
        state = "neutral"
        if freshness < 0.25 or reliability < 0.45:
            state = "warning"
            intensity *= 0.35
        elif expected_value > 0:
            state = "glow"
        else:
            intensity *= 0.45
        return HeatmapZone(
            start_price=0.0,
            end_price=0.0,
            intensity=max(0.05, min(intensity, 1.0)),
            state=state,  # type: ignore[arg-type]
            expected_value=expected_value,
            reliability=reliability,
            freshness_seconds=freshness_seconds,
            liquidity_score=liquidity_score,
        )

    def _build_insights(
        self,
        snapshot: TradeSnapshot,
        mfe: float,
        mae: float,
        realized: float,
        risk_distance: float,
    ) -> list[PostMortemInsight]:
        insights: list[PostMortemInsight] = []
        if mae > mfe and mae > risk_distance * 0.8:
            insights.append(
                PostMortemInsight(
                    code="sl_too_wide",
                    severity="warning",
                    message="The trade spent more room on adverse movement than favorable movement before exit.",
                    evidence={"mae": round(mae, 8), "mfe": round(mfe, 8), "risk_distance": round(risk_distance, 8)},
                )
            )
        if mfe < risk_distance * 0.6:
            insights.append(
                PostMortemInsight(
                    code="tp_too_far",
                    severity="warning",
                    message="Price never produced enough favorable excursion to justify the target distance.",
                    evidence={"mfe_r": round(mfe / risk_distance, 6), "target_rr": snapshot.rr},
                )
            )
        if snapshot.p_win > 0.7 and realized < 0:
            insights.append(
                PostMortemInsight(
                    code="ai_overconfidence",
                    severity="critical",
                    message="Stored win probability was high, but realized outcome was negative. Confidence calibration needs review.",
                    evidence={"p_win": snapshot.p_win, "realized_rr": round(realized / risk_distance, 6)},
                )
            )
        if not insights:
            insights.append(
                PostMortemInsight(
                    code="disciplined_execution",
                    severity="info",
                    message="The trade stayed within the planned structure and produced no obvious discipline breach.",
                    evidence={"realized_rr": round(realized / risk_distance, 6), "rr_planned": snapshot.rr},
                )
            )
        return insights
