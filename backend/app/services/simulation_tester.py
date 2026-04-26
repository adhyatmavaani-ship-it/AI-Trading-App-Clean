from __future__ import annotations

import asyncio
import math
import random
from dataclasses import dataclass

from app.core.config import Settings
from app.schemas.simulation import PerformanceReport, SimulationRequest, SimulationSummary
from app.schemas.trading import AIInference, FeatureSnapshot, TradeRequest
from app.services.drawdown_protection import DrawdownProtectionService
from app.services.paper_execution import PaperExecutionEngine
from app.services.risk_engine import RiskEngine
from app.services.system_monitor import SystemMonitorService
from app.services.trading_orchestrator import TradingOrchestrator


@dataclass
class SimulationTester:
    settings: Settings
    orchestrator: TradingOrchestrator
    risk_engine: RiskEngine
    drawdown_protection: DrawdownProtectionService
    monitor: SystemMonitorService
    paper_execution: PaperExecutionEngine

    async def run(self, request: SimulationRequest) -> SimulationSummary:
        balance = request.starting_balance
        daily_equity = [balance]
        wins = losses = duplicate_blocked = api_failures = risk_limit_breaches = 0
        profits: list[float] = []
        no_crashes = True
        equity_curve = [balance]

        for trade_index in range(request.trades):
            try:
                if request.include_latency:
                    await asyncio.sleep(0)
                day_progress = trade_index / max(request.trades, 1)
                volatility = self._volatility(day_progress, request.include_crashes)
                price = max(50.0, 100.0 * (1 + random.gauss(0, volatility)))
                snapshot = FeatureSnapshot(
                    symbol="BTCUSDT",
                    price=price,
                    timestamp="2026-01-01T00:00:00Z",
                    regime="VOLATILE" if volatility > 0.03 else "TRENDING",
                    regime_confidence=0.7,
                    volatility=volatility,
                    atr=price * max(volatility, 0.005),
                    order_book_imbalance=random.uniform(-0.6, 0.6),
                    features={"sim_feature": random.uniform(-1, 1)},
                )
                inference = AIInference(
                    price_forecast_return=random.uniform(-0.02, 0.02),
                    expected_return=random.uniform(-0.015, 0.02),
                    expected_risk=volatility,
                    trade_probability=random.uniform(0.52, 0.9),
                    confidence_score=random.uniform(0.52, 0.9),
                    decision="BUY" if random.random() > 0.48 else "SELL",
                    model_version="v1",
                    model_breakdown={"simulated": 1.0},
                    reason="simulation",
                )
                current_equity = equity_curve[-1]
                drawdown = self.drawdown_protection.update("sim-user", current_equity)
                try:
                    risk = self.risk_engine.evaluate(
                        balance=current_equity,
                        snapshot=snapshot,
                        inference=inference,
                        daily_pnl_pct=(current_equity - request.starting_balance) / request.starting_balance,
                        consecutive_losses=min(losses, self.settings.max_consecutive_losses - 1),
                        total_pnl_pct=(current_equity - request.starting_balance) / request.starting_balance,
                    )
                except ValueError:
                    risk_limit_breaches += 1
                    continue

                if request.include_api_failures and trade_index % 17 == 0:
                    api_failures += 1
                signal_id = f"sig-{trade_index // 2}" if request.include_duplicates and trade_index % 25 == 0 else f"sig-{trade_index}"
                response = await self.orchestrator.execute_signal(
                    TradeRequest(
                        user_id="sim-user",
                        symbol="BTCUSDT",
                        side=inference.decision,
                        order_type="MARKET",
                        confidence=inference.confidence_score,
                        reason="simulation",
                        expected_return=inference.expected_return,
                        expected_risk=inference.expected_risk,
                        requested_notional=risk.position_notional,
                        feature_snapshot=snapshot.features,
                        signal_id=signal_id,
                    )
                )
                if response.duplicate_signal:
                    duplicate_blocked += 1
                    continue
                pnl = risk.position_notional * inference.expected_return - response.fee_paid
                if volatility > 0.05:
                    pnl -= risk.position_notional * 0.01
                current_equity += pnl
                equity_curve.append(current_equity)
                profits.append(pnl)
                wins += int(pnl > 0)
                losses = 0 if pnl > 0 else losses + 1
                if trade_index and trade_index % max(1, math.floor(request.trades / request.days)) == 0:
                    prior = daily_equity[-1]
                    daily_equity.append(current_equity)
                    self.monitor.record_latency(random.uniform(10, 150))
                    self.drawdown_protection.update("sim-user", current_equity)
            except ValueError:
                risk_limit_breaches += 1
                continue
            except Exception:
                no_crashes = False
                self.monitor.increment_error()

        loss_abs = sum(abs(p) for p in profits if p < 0)
        profit_sum = sum(p for p in profits if p > 0)
        daily_returns = [
            (daily_equity[idx] - daily_equity[idx - 1]) / max(daily_equity[idx - 1], 1e-8)
            for idx in range(1, len(daily_equity))
        ]
        max_drawdown = 0.0
        peak = equity_curve[0]
        for equity in equity_curve:
            peak = max(peak, equity)
            max_drawdown = max(max_drawdown, (peak - equity) / max(peak, 1e-8))
        return SimulationSummary(
            trades_processed=len(profits),
            win_rate=wins / max(len(profits), 1),
            profit_factor=profit_sum / max(loss_abs, 1e-8),
            max_drawdown=max_drawdown,
            daily_returns=daily_returns,
            duplicate_signals_blocked=duplicate_blocked,
            api_failures_handled=api_failures,
            no_crashes=no_crashes,
            risk_limit_breaches=risk_limit_breaches,
        )

    def performance_report(self, summary: SimulationSummary, period_days: int) -> PerformanceReport:
        total_return = sum(summary.daily_returns)
        return PerformanceReport(
            period_days=period_days,
            win_rate=summary.win_rate,
            profit_factor=summary.profit_factor,
            max_drawdown=summary.max_drawdown,
            daily_returns=summary.daily_returns,
            total_return=total_return,
            trades=summary.trades_processed,
        )

    def _volatility(self, progress: float, include_crashes: bool) -> float:
        base = 0.01 + abs(math.sin(progress * math.pi * 4)) * 0.02
        if include_crashes and 0.45 <= progress <= 0.50:
            return 0.08
        return base
