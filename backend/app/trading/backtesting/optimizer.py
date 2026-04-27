from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json

from app.core.config import Settings
from app.schemas.backtest import (
    BacktestRequest,
    OptimizedStrategyResult,
    StrategyOptimizationRequest,
    StrategyOptimizationResponse,
)
from app.trading.backtesting.engine import TradingBacktestingEngine


@dataclass
class StrategyOptimizationEngine:
    settings: Settings
    backtester: TradingBacktestingEngine
    _cache: dict[str, tuple[datetime, StrategyOptimizationResponse]] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )

    async def optimize(self, request: StrategyOptimizationRequest, market_data) -> StrategyOptimizationResponse:
        cache_key = self._cache_key(request)
        if request.use_cache:
            cached = self._cache.get(cache_key)
            if cached is not None and cached[0] > datetime.now(timezone.utc):
                response = cached[1].model_copy(deep=True)
                response.cache_hit = True
                return response

        intervals = {request.timeframe}
        if request.strategy == "hybrid_crypto":
            intervals.update({"15m", "1h"})
        frames = await market_data.fetch_multi_timeframe_ohlcv(
            request.symbol,
            intervals=tuple(sorted(intervals)),
        )
        prepared_frames = {
            interval: self.backtester._prepare_frame(
                frame,
                BacktestRequest(
                    symbol=request.symbol,
                    timeframe=request.timeframe,
                    strategy=request.strategy,
                    starting_balance=request.starting_balance,
                    start_at=request.start_at,
                    end_at=request.end_at,
                    risk_profile="medium",
                ),
                timeframe=interval,
            )
            for interval, frame in frames.items()
        }

        runs = self._parameter_sets(request)
        if not runs:
            raise ValueError("No valid optimization parameter combinations were generated")

        max_workers = min(
            max(1, request.max_parallelism),
            max(1, self.settings.optimization_max_parallelism),
            len(runs),
        )
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [
                pool.submit(
                    self._run_single,
                    request,
                    prepared_frames,
                    params,
                )
                for params in runs
            ]
            responses = [future.result() for future in futures]

        ranked = sorted(
            (
                OptimizedStrategyResult(
                    rank=index + 1,
                    strategy=request.strategy,
                    parameters=response.strategy_params,
                    pnl=response.metrics.pnl,
                    max_drawdown=response.metrics.max_drawdown,
                    win_rate=response.metrics.win_rate,
                    trades=response.metrics.trades,
                    score=self._score(response),
                )
                for index, response in enumerate(
                    sorted(
                        responses,
                        key=self._score,
                        reverse=True,
                    )
                )
            ),
            key=lambda item: item.rank,
        )

        result = StrategyOptimizationResponse(
            symbol=request.symbol,
            strategy=request.strategy,
            best_parameters=ranked[0].parameters,
            best_result=ranked[0],
            rankings=ranked,
            total_runs=len(ranked),
            cache_hit=False,
        )
        if request.use_cache:
            self._cache[cache_key] = (
                datetime.now(timezone.utc) + timedelta(seconds=self.settings.optimization_cache_ttl_seconds),
                result.model_copy(deep=True),
            )
        return result

    def _run_single(self, request: StrategyOptimizationRequest, frames: dict, params: dict[str, int | float]):
        backtest_request = BacktestRequest(
            symbol=request.symbol,
            timeframe=request.timeframe,
            strategy=request.strategy,
            starting_balance=request.starting_balance,
            start_at=request.start_at,
            end_at=request.end_at,
            strategy_params=params,
            risk_profile="medium",
        )
        return self.backtester.run_prepared(request=backtest_request, frames=frames)

    def _parameter_sets(self, request: StrategyOptimizationRequest) -> list[dict[str, int | float]]:
        runs: list[dict[str, int | float]] = []
        if request.strategy == "ema_crossover":
            fast_periods = request.ema_fast_periods or [9, 12, 20]
            slow_periods = request.ema_slow_periods or [21, 26, 50]
            for fast in fast_periods:
                for slow in slow_periods:
                    if slow <= fast:
                        continue
                    runs.append(
                        {
                            "ema_fast_period": int(fast),
                            "ema_slow_period": int(slow),
                        }
                    )
            return runs

        if request.strategy == "rsi":
            periods = request.rsi_periods or [10, 14, 21]
            oversold_thresholds = request.rsi_oversold_thresholds or [25.0, 30.0, 35.0]
            overbought_thresholds = request.rsi_overbought_thresholds or [65.0, 70.0, 75.0]
            for period in periods:
                for oversold in oversold_thresholds:
                    for overbought in overbought_thresholds:
                        if oversold >= overbought:
                            continue
                        runs.append(
                            {
                                "rsi_period": int(period),
                                "rsi_oversold": float(oversold),
                                "rsi_overbought": float(overbought),
                            }
                        )
            return runs
        return runs

    def _score(self, response) -> float:
        return float(
            response.metrics.pnl
            + (response.metrics.win_rate * 1_000)
            - (response.metrics.max_drawdown * 500)
        )

    def _cache_key(self, request: StrategyOptimizationRequest) -> str:
        payload = json.dumps(request.model_dump(mode="json"), sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

