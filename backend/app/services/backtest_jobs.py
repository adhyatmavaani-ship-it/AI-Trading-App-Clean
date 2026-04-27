from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from app.core.config import Settings
from app.schemas.backtest import BacktestRequest
from app.schemas.backtest_jobs import (
    AsyncBacktestCompareRequest,
    AsyncBacktestRunRequest,
    BacktestComparisonProfileResult,
    BacktestEquityPoint,
    BacktestJobLog,
    BacktestJobResult,
    BacktestJobStatusResponse,
    BacktestJobSummary,
)

if TYPE_CHECKING:
    from app.services.backtesting import BacktestingEngine
    from app.services.historical_data import HistoricalDataService


@dataclass
class BacktestJobService:
    settings: Settings
    backtesting_engine: BacktestingEngine
    historical_data: HistoricalDataService
    _tasks: dict[str, asyncio.Task] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self.base_dir = Path(self.settings.backtest_data_dir)
        self.jobs_dir = self.base_dir / "jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    async def start(self) -> None:
        if not self.settings.backtest_resume_enabled:
            return
        for path in self.jobs_dir.glob("*.json"):
            payload = self._load_raw(path)
            if payload.get("status") not in {"QUEUED", "RUNNING"}:
                continue
            job_id = str(payload.get("job_id", "") or "")
            if not job_id or job_id in self._tasks:
                continue
            payload["status"] = "QUEUED"
            self._append_log(payload, "Recovered unfinished backtest job after restart.")
            self._persist(payload)
            self._tasks[job_id] = asyncio.create_task(self._run_job(job_id), name=f"backtest-job-{job_id}")

    async def stop(self) -> None:
        return None

    def enqueue(self, *, request: AsyncBacktestRunRequest, user_id: str) -> BacktestJobStatusResponse:
        return self._enqueue_payload(
            request=request.model_dump(mode="json"),
            user_id=user_id,
            mode="single",
            description=f"Queued {request.strategy} backtest for {request.symbol.upper()} over {request.days} day(s).",
        )

    def enqueue_compare(
        self,
        *,
        request: AsyncBacktestCompareRequest,
        user_id: str,
    ) -> BacktestJobStatusResponse:
        normalized_profiles = list(dict.fromkeys(request.profiles or ["low", "high"]))
        compare_request = request.model_copy(update={"profiles": normalized_profiles})
        return self._enqueue_payload(
            request=compare_request.model_dump(mode="json"),
            user_id=user_id,
            mode="compare",
            description=(
                f"Queued comparison backtest for {request.symbol.upper()} "
                f"with profiles {', '.join(profile.upper() for profile in normalized_profiles)}."
            ),
        )

    def _enqueue_payload(
        self,
        *,
        request: dict,
        user_id: str,
        mode: str,
        description: str,
    ) -> BacktestJobStatusResponse:
        created_at = datetime.now(timezone.utc)
        job_id = str(uuid4())
        payload = {
            "job_id": job_id,
            "user_id": user_id,
            "mode": mode,
            "status": "QUEUED",
            "progress_pct": 0.0,
            "current_stage": "queued",
            "trades_found": 0,
            "net_profit": 0.0,
            "heartbeat_at": created_at.isoformat(),
            "created_at": created_at.isoformat(),
            "started_at": None,
            "completed_at": None,
            "error": None,
            "logs": [],
            "request": request,
            "result": None,
            "comparison_profiles": [],
        }
        self._append_log(payload, description)
        self._persist(payload)
        self._tasks[job_id] = asyncio.create_task(self._run_job(job_id), name=f"backtest-job-{job_id}")
        return self.status(job_id)

    def status(self, job_id: str) -> BacktestJobStatusResponse:
        payload = self._load(job_id)
        if payload is None:
            raise ValueError(f"Unknown backtest job: {job_id}")
        return BacktestJobStatusResponse.model_validate(payload)

    async def _run_job(self, job_id: str) -> None:
        payload = self._load(job_id)
        if payload is None:
            return
        try:
            mode = str(payload.get("mode", "single") or "single")
            started_at = datetime.now(timezone.utc)
            payload["status"] = "RUNNING"
            payload["started_at"] = started_at.isoformat()
            payload["heartbeat_at"] = started_at.isoformat()
            payload["current_stage"] = "fetching_historical_data"
            self._append_log(payload, "Fetching historical OHLCV chunks from cache/Binance.")
            self._persist(payload)

            if mode == "compare":
                request = AsyncBacktestCompareRequest.model_validate(payload.get("request") or {})
            else:
                request = AsyncBacktestRunRequest.model_validate(payload.get("request") or {})
            end_at = datetime.now(timezone.utc)
            start_at = end_at - timedelta(days=int(request.days))
            intervals = self._required_intervals(request.strategy, request.timeframe)
            total_chunks = max(1, len(intervals) * request.days)
            loaded_frames = {}
            completed_chunks = 0

            for interval in intervals:
                async def on_chunk(chunk_start, chunk_end, frame, *, active_interval=interval):
                    nonlocal completed_chunks, payload
                    completed_chunks += 1
                    payload["heartbeat_at"] = datetime.now(timezone.utc).isoformat()
                    payload["progress_pct"] = round(min(70.0, (completed_chunks / total_chunks) * 70.0), 2)
                    payload["current_stage"] = "fetching_historical_data"
                    rows = int(len(frame))
                    self._append_log(
                        payload,
                        f"Loaded {active_interval} chunk for {request.symbol.upper()} {chunk_start.date()} ({rows} rows).",
                    )
                    self._persist(payload)

                loaded_frames[interval] = await self.historical_data.load_range(
                    symbol=request.symbol.upper(),
                    timeframe=interval,
                    start_at=start_at,
                    end_at=end_at,
                    on_chunk=on_chunk,
                )

            payload["progress_pct"] = 78.0
            payload["current_stage"] = "preparing_replay"
            payload["heartbeat_at"] = datetime.now(timezone.utc).isoformat()
            self._append_log(payload, "Preparing cached data for strategy replay.")
            self._persist(payload)

            backtester = self.backtesting_engine.optimizer.backtester
            if mode == "compare":
                baseline_request = BacktestRequest(
                    symbol=request.symbol.upper(),
                    timeframe=request.timeframe,
                    strategy=request.strategy,
                    starting_balance=request.starting_balance,
                    start_at=start_at,
                    end_at=end_at,
                    strategy_params={},
                    risk_profile="medium",
                )
                prepared_frames = {
                    interval: backtester._prepare_frame(frame, baseline_request, timeframe=interval)
                    for interval, frame in loaded_frames.items()
                }
                await self._run_compare_profiles(
                    payload=payload,
                    request=request,
                    backtester=backtester,
                    prepared_frames=prepared_frames,
                    start_at=start_at,
                    end_at=end_at,
                )
            else:
                backtest_request = BacktestRequest(
                    symbol=request.symbol.upper(),
                    timeframe=request.timeframe,
                    strategy=request.strategy,
                    starting_balance=request.starting_balance,
                    start_at=start_at,
                    end_at=end_at,
                    strategy_params={},
                    risk_profile=request.risk_profile,
                )
                prepared_frames = {
                    interval: backtester._prepare_frame(frame, backtest_request, timeframe=interval)
                    for interval, frame in loaded_frames.items()
                }
                payload["progress_pct"] = 86.0
                payload["current_stage"] = "running_strategy_replay"
                payload["heartbeat_at"] = datetime.now(timezone.utc).isoformat()
                self._append_log(payload, "Running lightweight strategy replay.")
                self._persist(payload)

                response = backtester.run_prepared(request=backtest_request, frames=prepared_frames)

                payload["progress_pct"] = 96.0
                payload["current_stage"] = "finalizing_report"
                payload["trades_found"] = int(response.metrics.trades)
                payload["net_profit"] = float(response.metrics.pnl)
                payload["heartbeat_at"] = datetime.now(timezone.utc).isoformat()
                self._append_log(payload, f"Replay complete with {response.metrics.trades} trade(s). Building report.")

                payload["result"] = self._single_result_payload(
                    response=response,
                    symbol=request.symbol.upper(),
                    timeframe=request.timeframe,
                    strategy=request.strategy,
                    days=int(request.days),
                    starting_balance=float(request.starting_balance),
                )
            payload["status"] = "COMPLETED"
            payload["progress_pct"] = 100.0
            payload["current_stage"] = "completed"
            payload["completed_at"] = datetime.now(timezone.utc).isoformat()
            payload["heartbeat_at"] = payload["completed_at"]
            self._append_log(payload, "Backtest report is ready.")
            self._persist(payload)
        except Exception as exc:  # pragma: no cover - integration path
            payload = self._load(job_id) or payload or {}
            payload["status"] = "FAILED"
            payload["current_stage"] = "failed"
            payload["completed_at"] = datetime.now(timezone.utc).isoformat()
            payload["heartbeat_at"] = payload["completed_at"]
            payload["error"] = str(exc)
            self._append_log(payload, f"Backtest failed: {str(exc)[:200]}")
            self._persist(payload)
        finally:
            self._tasks.pop(job_id, None)

    def _required_intervals(self, strategy: str, timeframe: str) -> list[str]:
        intervals = {timeframe}
        if strategy == "hybrid_crypto":
            intervals.update({"15m", "1h"})
        return sorted(intervals)

    def _load(self, job_id: str) -> dict | None:
        path = self.jobs_dir / f"{job_id}.json"
        if not path.exists():
            return None
        return self._load_raw(path)

    def _load_raw(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def _persist(self, payload: dict) -> None:
        keep_logs = max(int(self.settings.backtest_status_log_limit), 1)
        payload["logs"] = list(payload.get("logs", []))[-keep_logs:]
        path = self.jobs_dir / f"{payload['job_id']}.json"
        path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    def _append_log(self, payload: dict, message: str) -> None:
        logs = list(payload.get("logs", []))
        logs.append(
            BacktestJobLog(
                timestamp=datetime.now(timezone.utc),
                message=message,
            ).model_dump(mode="json")
        )
        payload["logs"] = logs

    async def _run_compare_profiles(
        self,
        *,
        payload: dict,
        request: AsyncBacktestCompareRequest,
        backtester,
        prepared_frames: dict,
        start_at: datetime,
        end_at: datetime,
    ) -> None:
        profile_results: list[dict] = []
        profiles = list(request.profiles or ["low", "high"])
        total_profiles = max(len(profiles), 1)
        for index, profile in enumerate(profiles, start=1):
            payload["progress_pct"] = round(82.0 + ((index - 1) / total_profiles) * 12.0, 2)
            payload["current_stage"] = f"running_{profile}_profile"
            payload["heartbeat_at"] = datetime.now(timezone.utc).isoformat()
            self._append_log(payload, f"Running sequential replay for {profile.upper()} risk profile.")
            self._persist(payload)
            backtest_request = BacktestRequest(
                symbol=request.symbol.upper(),
                timeframe=request.timeframe,
                strategy=request.strategy,
                starting_balance=request.starting_balance,
                start_at=start_at,
                end_at=end_at,
                strategy_params={},
                risk_profile=profile,
            )
            response = backtester.run_prepared(request=backtest_request, frames=prepared_frames)
            profile_result = BacktestComparisonProfileResult(
                risk_profile=profile,
                summary=BacktestJobSummary(
                    symbol=request.symbol.upper(),
                    timeframe=request.timeframe,
                    strategy=request.strategy,
                    days=int(request.days),
                    starting_balance=float(request.starting_balance),
                    final_equity=round(float(request.starting_balance) + float(response.metrics.pnl), 8),
                    total_profit=round(float(response.metrics.pnl), 8),
                    roi_pct=round(float(response.metrics.total_return) * 100.0, 8),
                    win_rate=round(float(response.metrics.win_rate), 8),
                    max_drawdown=round(float(response.metrics.max_drawdown), 8),
                    profit_factor=round(float(response.metrics.profit_factor), 8),
                    total_trades=int(response.metrics.trades),
                ),
                equity_curve=[
                    BacktestEquityPoint(
                        step=int(point.step),
                        equity=float(point.equity),
                        regime=str(point.regime),
                    )
                    for point in response.equity_curve
                ],
                trades=[trade.model_dump(mode="json") for trade in response.trades],
            ).model_dump(mode="json")
            profile_results.append(profile_result)
            payload["trades_found"] += int(response.metrics.trades)
            payload["net_profit"] += float(response.metrics.pnl)
            payload["comparison_profiles"] = profile_results
            self._append_log(
                payload,
                f"{profile.upper()} profile finished: ROI {profile_result['summary']['roi_pct']:.2f}% | trades {profile_result['summary']['total_trades']}.",
            )
            self._persist(payload)

    def _single_result_payload(
        self,
        *,
        response,
        symbol: str,
        timeframe: str,
        strategy: str,
        days: int,
        starting_balance: float,
    ) -> dict:
        final_equity = float(starting_balance) + float(response.metrics.pnl)
        return BacktestJobResult(
            summary=BacktestJobSummary(
                symbol=symbol,
                timeframe=timeframe,
                strategy=strategy,
                days=days,
                starting_balance=float(starting_balance),
                final_equity=round(final_equity, 8),
                total_profit=round(float(response.metrics.pnl), 8),
                roi_pct=round(float(response.metrics.total_return) * 100.0, 8),
                win_rate=round(float(response.metrics.win_rate), 8),
                max_drawdown=round(float(response.metrics.max_drawdown), 8),
                profit_factor=round(float(response.metrics.profit_factor), 8),
                total_trades=int(response.metrics.trades),
            ),
            equity_curve=[
                BacktestEquityPoint(
                    step=int(point.step),
                    equity=float(point.equity),
                    regime=str(point.regime),
                )
                for point in response.equity_curve
            ],
            trades=[trade.model_dump(mode="json") for trade in response.trades],
        ).model_dump(mode="json")

    def export_csv(self, job_id: str) -> tuple[str, str]:
        payload = self._load(job_id)
        if payload is None:
            raise ValueError(f"Unknown backtest job: {job_id}")
        rows: list[dict] = []
        if payload.get("comparison_profiles"):
            for profile_payload in payload.get("comparison_profiles", []):
                risk_profile = str(profile_payload.get("risk_profile", "") or "")
                for trade in profile_payload.get("trades", []) or []:
                    rows.append({"risk_profile": risk_profile, **dict(trade)})
        elif payload.get("result"):
            for trade in (payload.get("result", {}) or {}).get("trades", []) or []:
                rows.append({"risk_profile": str((payload.get("request") or {}).get("risk_profile", "medium")), **dict(trade)})
        header = ["risk_profile", "side", "entry", "exit", "profit", "confidence", "regime", "reason"]
        lines = [",".join(header)]
        for row in rows:
            values = []
            for column in header:
                value = str(row.get(column, "") or "").replace('"', '""')
                values.append(f'"{value}"')
            lines.append(",".join(values))
        return f"backtest_{job_id}.csv", "\n".join(lines)
