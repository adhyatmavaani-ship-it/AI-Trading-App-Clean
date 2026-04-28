from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone

import pandas as pd

from app.schemas.backtest import (
    BacktestMetrics,
    BacktestRequest,
    BacktestResponse,
    BacktestTrade,
    EquityPoint,
)
from app.trading.exits import compute_trailing_multiplier, evaluate_exit
from app.trading.risk.manager import TradingRiskManager
from app.trading.strategies.engine import TradingStrategyEngine


@dataclass
class TradingBacktestingEngine:
    strategy_engine: TradingStrategyEngine
    risk_manager: TradingRiskManager
    fee_rate: float = 0.001
    slippage_rate: float = 0.001

    async def run(self, request: BacktestRequest, market_data) -> BacktestResponse:
        intervals = {request.timeframe}
        if request.strategy == "hybrid_crypto":
            intervals.update({"15m", "1h"})
        frames = await market_data.fetch_multi_timeframe_ohlcv(
            request.symbol,
            intervals=tuple(sorted(intervals)),
        )
        prepared_frames = {
            interval: self._prepare_frame(frame, request, timeframe=interval)
            for interval, frame in frames.items()
        }
        return self.run_prepared(
            request=request,
            frames=prepared_frames,
        )

    def run_prepared(
        self,
        *,
        request: BacktestRequest,
        frames: dict[str, pd.DataFrame],
    ) -> BacktestResponse:
        frame = frames[request.timeframe]
        if len(frame) < 35:
            raise ValueError("Not enough historical data for backtest")

        equity = request.starting_balance
        daily_start_equity = equity
        current_day = None
        position: dict | None = None
        realized_pnl = 0.0
        trades: list[BacktestTrade] = []
        equity_curve: list[EquityPoint] = []
        peak_equity = equity
        max_drawdown = 0.0
        profile_controls = self._profile_controls(request.risk_profile)
        confidence_floor = self._effective_confidence_floor(
            strategy=request.strategy,
            base_floor=float(profile_controls["confidence_floor"]),
        )

        for idx in range(30, len(frame)):
            row = frame.iloc[idx]
            timestamp = pd.Timestamp(row["timestamp"]).to_pydatetime().astimezone(timezone.utc)
            if current_day != timestamp.date():
                current_day = timestamp.date()
                daily_start_equity = equity

            mark_equity = equity
            if position is not None:
                unrealized = self._unrealized_pnl(
                    position=position,
                    close_price=float(row["close"]),
                )
                mark_equity += unrealized

            peak_equity = max(peak_equity, mark_equity)
            max_drawdown = max(
                max_drawdown,
                (peak_equity - mark_equity) / max(peak_equity, 1e-8),
            )
            equity_curve.append(
                EquityPoint(
                    step=len(equity_curve),
                    equity=round(mark_equity, 8),
                    regime=str(row.get("regime", "UNKNOWN")),
                )
            )

            if idx == len(frame) - 1:
                if position is not None:
                    pnl = self._close_position(position, float(row["close"]))
                    total_trade_pnl = float(position.get("booked_pnl", 0.0) or 0.0) + pnl
                    realized_pnl += pnl
                    equity += pnl
                    trades.append(
                        BacktestTrade(
                            side=position["side"],
                            entry=position["entry_price"],
                            exit=float(row["close"]),
                            profit=round(total_trade_pnl, 8),
                            confidence=position["confidence"],
                            regime=position["regime"],
                            reason=position["strategy"],
                        )
                    )
                break

            window = self._window_for_index(frames, idx, request.timeframe)
            decision = self.strategy_engine.evaluate(
                window if request.strategy == "hybrid_crypto" else window[request.timeframe],
                preferred_strategy=request.strategy,
                strategy_params=request.strategy_params,
            )

            if position is not None:
                had_partial_take_profit = bool(position.get("partial_take_profit_taken", False))
                atr = self._atr(window)
                volatility = self._volatility(window)
                regime = self._regime(window)
                trailing_multiplier = compute_trailing_multiplier(
                    settings=self.risk_manager.settings,
                    volatility=volatility,
                    regime=regime,
                    adx=float(decision.metadata.get("adx", 0.0) or 0.0),
                    adaptive_value=1.0,
                )
                evaluation = evaluate_exit(
                    settings=self.risk_manager.settings,
                    trade=position,
                    latest_price=float(row["close"]),
                    atr=atr,
                    regime=regime,
                    volatility=volatility,
                    frame=window[request.timeframe],
                    trailing_multiplier=trailing_multiplier,
                    structure_break=decision.signal != "HOLD" and decision.signal != position["side"],
                    stop_hit=self._stop_hit(position, row),
                )
                position["stop_loss"] = float(evaluation.stop_loss)
                position["trailing_stop_pct"] = float(evaluation.trailing_stop_pct)
                position["take_profit"] = float(evaluation.take_profit)
                position["partial_take_profit_taken"] = bool(
                    had_partial_take_profit or evaluation.partial_take_profit_taken
                )
                if (
                    evaluation.action == "partial_close"
                    and not had_partial_take_profit
                ):
                    partial_fraction = float(profile_controls["partial_fraction"])
                    pnl = self._close_position_quantity(
                        position,
                        exit_price=float(row["close"]),
                        close_fraction=partial_fraction,
                    )
                    realized_pnl += pnl
                    equity += pnl
                    position["booked_pnl"] = round(float(position.get("booked_pnl", 0.0) or 0.0) + pnl, 8)
                elif evaluation.action == "full_close":
                    exit_price = (
                        float(position["stop_loss"])
                        if evaluation.exit_type == "stop_loss"
                        else float(row["close"])
                    )
                    remaining_pnl = self._close_position_quantity(
                        position,
                        exit_price=exit_price,
                        close_fraction=1.0,
                    )
                    total_trade_pnl = float(position.get("booked_pnl", 0.0) or 0.0) + remaining_pnl
                    realized_pnl += remaining_pnl
                    equity += remaining_pnl
                    trades.append(
                        BacktestTrade(
                            side=position["side"],
                            entry=position["entry_price"],
                            exit=exit_price,
                            profit=round(total_trade_pnl, 8),
                            confidence=position["confidence"],
                            regime=position["regime"],
                            reason=f"{position['strategy']}:{evaluation.exit_reason}",
                        )
                    )
                    position = None
                    continue

            daily_pnl_pct = (
                (equity - daily_start_equity) / max(daily_start_equity, 1e-8)
                if daily_start_equity
                else 0.0
            )
            if position is None and decision.signal != "HOLD":
                if float(decision.confidence) < confidence_floor:
                    continue
                next_open = float(frame.iloc[idx + 1]["open"])
                entry_price = self._execution_price(next_open, decision.signal)
                atr = self._atr(window)
                try:
                    risk = self.risk_manager.evaluate(
                        balance=equity,
                        price=entry_price,
                        volatility=self._volatility(window),
                        atr=atr,
                        decision=decision.signal,
                        confidence=decision.confidence,
                        daily_pnl_pct=daily_pnl_pct,
                        consecutive_losses=0,
                        regime=self._regime(window),
                        trade_success_probability=float(
                            decision.metadata.get("trade_success_probability", decision.confidence)
                        ),
                        stop_loss_multiplier=float(profile_controls["stop_multiplier"]),
                        trade_intelligence_metrics={
                            "win_rate": float(decision.metadata.get("meta_model_regime_win_rate", 0.5)),
                            "avg_r_multiple": float(decision.metadata.get("meta_model_avg_r_multiple", 0.0)),
                            "avg_drawdown": float(decision.metadata.get("meta_model_avg_drawdown", 0.0)),
                        },
                    )
                except ValueError:
                    continue
                effective_notional = min(
                    float(risk.position_notional),
                    float(equity) * float(profile_controls["risk_fraction"]),
                )
                quantity = effective_notional / max(entry_price, 1e-8)
                entry_fee = effective_notional * self.fee_rate
                position = {
                    "side": decision.signal,
                    "entry_price": entry_price,
                    "quantity": quantity,
                    "entry_fee_remaining": entry_fee,
                    "stop_loss": float(risk.stop_loss),
                    "initial_stop_loss": float(risk.stop_loss),
                    "trailing_stop_pct": float(risk.trailing_stop_pct),
                    "take_profit": entry_price + (abs(entry_price - float(risk.stop_loss)) * float(self.risk_manager.settings.strict_trade_min_take_profit_rr))
                    if decision.signal == "BUY"
                    else entry_price - (abs(entry_price - float(risk.stop_loss)) * float(self.risk_manager.settings.strict_trade_min_take_profit_rr)),
                    "confidence": decision.confidence,
                    "strategy": decision.strategy,
                    "regime": self._regime(window),
                    "risk_profile": request.risk_profile,
                    "booked_pnl": 0.0,
                    "partial_take_profit_taken": False,
                }

        wins = sum(1 for trade in trades if trade.profit > 0)
        pnl = realized_pnl
        win_rate = wins / len(trades) if trades else 0.0
        return BacktestResponse(
            symbol=request.symbol,
            metrics=BacktestMetrics(
                pnl=round(pnl, 8),
                win_rate=win_rate,
                sharpe_ratio=self._sharpe(trades),
                sortino_ratio=self._sortino(trades),
                max_drawdown=float(max_drawdown),
                profit_factor=self._profit_factor(trades),
                max_win_streak=self._streak(trades, won=True),
                max_loss_streak=self._streak(trades, won=False),
                total_return=pnl / max(request.starting_balance, 1e-8),
                trades=len(trades),
            ),
            trades=trades,
            equity_curve=equity_curve,
            strategy=request.strategy,
            strategy_params=request.strategy_params,
        )

    def _profile_controls(self, risk_profile: str) -> dict[str, float]:
        normalized = str(risk_profile or "medium").lower()
        if normalized == "low":
            return {
                "confidence_floor": 0.85,
                "risk_fraction": 0.005,
                "stop_multiplier": 0.7,
                "partial_fraction": float(self.risk_manager.settings.strict_trade_partial_take_profit_fraction),
            }
        if normalized == "high":
            return {
                "confidence_floor": 0.60,
                "risk_fraction": 0.015,
                "stop_multiplier": 1.3,
                "partial_fraction": float(self.risk_manager.settings.strict_trade_partial_take_profit_fraction),
            }
        return {
            "confidence_floor": 0.70,
            "risk_fraction": 0.01,
            "stop_multiplier": 1.0,
            "partial_fraction": float(self.risk_manager.settings.strict_trade_partial_take_profit_fraction),
        }

    def _effective_confidence_floor(self, *, strategy: str, base_floor: float) -> float:
        normalized = str(strategy or "").lower()
        if normalized in {"ema_crossover", "rsi", "breakout"}:
            return min(base_floor, 0.45)
        return base_floor

    def _prepare_frame(
        self,
        frame: pd.DataFrame,
        request: BacktestRequest,
        *,
        timeframe: str,
    ) -> pd.DataFrame:
        prepared = frame.copy()
        if "open_time" in prepared.columns:
            prepared["timestamp"] = pd.to_datetime(prepared["open_time"], unit="ms", utc=True)
        else:
            prepared["timestamp"] = pd.date_range(
                end=pd.Timestamp.now(tz="UTC"),
                periods=len(prepared),
                freq=self._pandas_freq(timeframe),
            )
        for column in ("open", "high", "low", "close", "volume"):
            prepared[column] = prepared[column].astype(float)
        prepared = prepared[
            (prepared["timestamp"] >= request.start_at)
            & (prepared["timestamp"] <= request.end_at)
        ]
        if prepared.empty:
            prepared = frame.copy()
            if "open_time" in prepared.columns:
                prepared["timestamp"] = pd.to_datetime(prepared["open_time"], unit="ms", utc=True)
            else:
                prepared["timestamp"] = pd.date_range(
                    end=pd.Timestamp.now(tz="UTC"),
                    periods=len(prepared),
                    freq=self._pandas_freq(timeframe),
                )
            for column in ("open", "high", "low", "close", "volume"):
                prepared[column] = prepared[column].astype(float)
        return prepared.reset_index(drop=True)

    def _window_for_index(
        self,
        frames: dict[str, pd.DataFrame],
        idx: int,
        primary_timeframe: str,
    ) -> dict[str, pd.DataFrame]:
        primary = frames[primary_timeframe]
        timestamp = pd.Timestamp(primary.iloc[idx]["timestamp"])
        windows: dict[str, pd.DataFrame] = {}
        for timeframe, frame in frames.items():
            subset = frame[frame["timestamp"] <= timestamp].copy()
            if subset.empty:
                subset = frame.iloc[: min(idx + 1, len(frame))].copy()
            windows[timeframe] = subset.reset_index(drop=True)
        return windows

    def _pandas_freq(self, timeframe: str) -> str:
        mapping = {"1m": "1min", "5m": "5min", "15m": "15min", "1h": "1h"}
        return mapping.get(timeframe, timeframe)

    def _execution_price(self, raw_price: float, side: str) -> float:
        if side == "BUY":
            return raw_price * (1 + self.slippage_rate)
        return raw_price * (1 - self.slippage_rate)

    def _close_position(self, position: dict, exit_price: float) -> float:
        return self._close_position_quantity(position, exit_price=exit_price, close_fraction=1.0)

    def _close_position_quantity(self, position: dict, *, exit_price: float, close_fraction: float) -> float:
        current_quantity = float(position["quantity"])
        quantity_to_close = min(current_quantity, current_quantity * float(close_fraction))
        if quantity_to_close <= 0:
            return 0.0
        direction = 1.0 if position["side"] == "BUY" else -1.0
        gross = (exit_price - position["entry_price"]) * quantity_to_close * direction
        exit_notional = abs(exit_price * quantity_to_close)
        exit_fee = exit_notional * self.fee_rate
        entry_fee_remaining = float(position.get("entry_fee_remaining", 0.0) or 0.0)
        entry_fee_allocated = entry_fee_remaining * (quantity_to_close / max(current_quantity, 1e-8))
        position["quantity"] = round(max(0.0, current_quantity - quantity_to_close), 8)
        position["entry_fee_remaining"] = round(max(0.0, entry_fee_remaining - entry_fee_allocated), 8)
        return gross - entry_fee_allocated - exit_fee

    def _unrealized_pnl(self, *, position: dict, close_price: float) -> float:
        direction = 1.0 if position["side"] == "BUY" else -1.0
        gross = (close_price - position["entry_price"]) * position["quantity"] * direction
        return gross - float(position.get("entry_fee_remaining", 0.0) or 0.0)

    def _stop_hit(self, position: dict, row: pd.Series) -> bool:
        if position["side"] == "BUY":
            return float(row["low"]) <= float(position["stop_loss"])
        return float(row["high"]) >= float(position["stop_loss"])

    def _atr(self, frame: pd.DataFrame | dict[str, pd.DataFrame], period: int = 14) -> float:
        working = self._frame(frame)
        high = working["high"].astype(float)
        low = working["low"].astype(float)
        close = working["close"].astype(float)
        previous_close = close.shift(1)
        true_range = pd.concat(
            [
                (high - low),
                (high - previous_close).abs(),
                (low - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr = true_range.rolling(period).mean().iloc[-1]
        return float(atr if pd.notna(atr) else max((high - low).iloc[-1], close.iloc[-1] * 0.005))

    def _volatility(self, frame: pd.DataFrame | dict[str, pd.DataFrame], period: int = 20) -> float:
        working = self._frame(frame)
        returns = working["close"].astype(float).pct_change().dropna()
        if returns.empty:
            return 0.0
        sample = returns.tail(period)
        return float(sample.std())

    def _regime(self, frame: pd.DataFrame | dict[str, pd.DataFrame]) -> str:
        working = self._frame(frame)
        closes = working["close"].astype(float)
        if len(closes) < 20:
            return "RANGING"
        if closes.iloc[-1] > closes.rolling(20).mean().iloc[-1]:
            return "TRENDING"
        return "RANGING"

    def _frame(self, frame: pd.DataFrame | dict[str, pd.DataFrame]) -> pd.DataFrame:
        if isinstance(frame, dict):
            preferred = frame.get("5m")
            if preferred is None:
                preferred = frame.get("15m")
            if preferred is None:
                preferred = frame[next(iter(frame))]
            return preferred
        return frame

    def _profit_factor(self, trades: list[BacktestTrade]) -> float:
        gross_profit = sum(trade.profit for trade in trades if trade.profit > 0)
        gross_loss = abs(sum(trade.profit for trade in trades if trade.profit < 0))
        return gross_profit / max(gross_loss, 1e-8)

    def _streak(self, trades: list[BacktestTrade], *, won: bool) -> int:
        best = current = 0
        for trade in trades:
            matched = trade.profit > 0 if won else trade.profit < 0
            if matched:
                current += 1
                best = max(best, current)
            else:
                current = 0
        return best

    def _sharpe(self, trades: list[BacktestTrade]) -> float:
        returns = pd.Series([trade.profit for trade in trades], dtype=float)
        if returns.empty or float(returns.std() or 0.0) == 0.0:
            return 0.0
        return float((returns.mean() / returns.std()) * (len(returns) ** 0.5))

    def _sortino(self, trades: list[BacktestTrade]) -> float:
        returns = pd.Series([trade.profit for trade in trades], dtype=float)
        downside = returns[returns < 0]
        if returns.empty or downside.empty or float(downside.std() or 0.0) == 0.0:
            return self._sharpe(trades)
        return float((returns.mean() / downside.std()) * (len(returns) ** 0.5))

