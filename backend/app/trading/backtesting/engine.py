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
                    realized_pnl += pnl
                    equity += pnl
                    trades.append(
                        BacktestTrade(
                            side=position["side"],
                            entry=position["entry_price"],
                            exit=float(row["close"]),
                            profit=round(pnl, 8),
                            confidence=position["confidence"],
                            regime=position["regime"],
                            reason=position["strategy"],
                        )
                    )
                break

            if position is not None and self._stop_hit(position, row):
                exit_price = float(position["stop_loss"])
                pnl = self._close_position(position, exit_price)
                realized_pnl += pnl
                equity += pnl
                trades.append(
                    BacktestTrade(
                        side=position["side"],
                        entry=position["entry_price"],
                        exit=exit_price,
                        profit=round(pnl, 8),
                        confidence=position["confidence"],
                        regime=position["regime"],
                        reason=f"{position['strategy']}:stop",
                    )
                )
                position = None
                continue

            window = self._window_for_index(frames, idx, request.timeframe)
            decision = self.strategy_engine.evaluate(
                window if request.strategy == "hybrid_crypto" else window[request.timeframe],
                preferred_strategy=request.strategy,
                strategy_params=request.strategy_params,
            )

            if position is not None and decision.signal != "HOLD" and decision.signal != position["side"]:
                exit_price = self._execution_price(
                    raw_price=float(frame.iloc[idx + 1]["open"]),
                    side="SELL" if position["side"] == "BUY" else "BUY",
                )
                pnl = self._close_position(position, exit_price)
                realized_pnl += pnl
                equity += pnl
                trades.append(
                    BacktestTrade(
                        side=position["side"],
                        entry=position["entry_price"],
                        exit=exit_price,
                        profit=round(pnl, 8),
                        confidence=position["confidence"],
                        regime=position["regime"],
                        reason=f"{position['strategy']}:flip",
                    )
                )
                position = None

            daily_pnl_pct = (
                (equity - daily_start_equity) / max(daily_start_equity, 1e-8)
                if daily_start_equity
                else 0.0
            )
            if position is None and decision.signal != "HOLD":
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
                        trade_intelligence_metrics={
                            "win_rate": float(decision.metadata.get("meta_model_regime_win_rate", 0.5)),
                            "avg_r_multiple": float(decision.metadata.get("meta_model_avg_r_multiple", 0.0)),
                            "avg_drawdown": float(decision.metadata.get("meta_model_avg_drawdown", 0.0)),
                        },
                    )
                except ValueError:
                    continue
                quantity = risk.position_notional / max(entry_price, 1e-8)
                entry_fee = risk.position_notional * self.fee_rate
                position = {
                    "side": decision.signal,
                    "entry_price": entry_price,
                    "quantity": quantity,
                    "entry_fee": entry_fee,
                    "stop_loss": risk.stop_loss,
                    "confidence": decision.confidence,
                    "strategy": decision.strategy,
                    "regime": self._regime(window),
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
        direction = 1.0 if position["side"] == "BUY" else -1.0
        gross = (exit_price - position["entry_price"]) * position["quantity"] * direction
        exit_notional = abs(exit_price * position["quantity"])
        exit_fee = exit_notional * self.fee_rate
        return gross - position["entry_fee"] - exit_fee

    def _unrealized_pnl(self, *, position: dict, close_price: float) -> float:
        direction = 1.0 if position["side"] == "BUY" else -1.0
        gross = (close_price - position["entry_price"]) * position["quantity"] * direction
        return gross - position["entry_fee"]

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

