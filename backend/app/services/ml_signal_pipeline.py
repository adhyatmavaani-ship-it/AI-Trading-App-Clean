from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import math
from typing import Protocol

from app.schemas.advanced_trading import AiStrategyContextRequest
from app.services.advanced_trading_state import AdvancedTradingStateRepository


@dataclass(frozen=True)
class MarketFrame:
    symbol: str
    prices: list[float]
    volumes: list[float]
    observed_at: datetime


class MarketSignalSource(Protocol):
    async def next_frame(self) -> MarketFrame:
        ...


class DeterministicMarketSignalSource:
    """Replay-safe source used when live exchange streaming is not configured."""

    def __init__(self, symbol: str = "BTCUSDT") -> None:
        self._symbol = symbol.upper()
        self._tick = 0

    async def next_frame(self) -> MarketFrame:
        self._tick += 1
        base = 68_000 + (self._stable_offset(self._symbol) % 2_000)
        prices = [
            round(base + math.sin((self._tick + index) / 5) * 120 + index * 2.5, 2)
            for index in range(64)
        ]
        volumes = [round(100 + abs(math.cos((self._tick + index) / 8)) * 40, 2) for index in range(64)]
        return MarketFrame(
            symbol=self._symbol,
            prices=prices,
            volumes=volumes,
            observed_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _stable_offset(value: str) -> int:
        return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:8], 16)


class LocalMomentumInferenceEngine:
    """Small deterministic inference shim until local model artifacts are wired."""

    def infer(self, frame: MarketFrame) -> dict[str, object]:
        if len(frame.prices) < 2:
            momentum = 0.0
        else:
            momentum = (frame.prices[-1] - frame.prices[0]) / max(frame.prices[0], 1e-9)
        volatility = self._std(frame.prices) / max(sum(frame.prices) / len(frame.prices), 1e-9)
        volume_pressure = (frame.volumes[-1] - frame.volumes[0]) / max(frame.volumes[0], 1e-9)
        confidence = max(0.0, min(0.99, 0.52 + abs(momentum) * 8 + max(volume_pressure, 0) * 0.05))
        side = "BUY" if momentum >= 0 else "SELL"
        forecast = [
            {
                "step": step,
                "price": round(frame.prices[-1] * (1 + momentum * (step / 8)), 2),
            }
            for step in range(1, 9)
        ]
        return {
            "side": side,
            "confidence": round(confidence, 4),
            "momentum": round(momentum, 6),
            "volatility": round(volatility, 6),
            "volume_pressure": round(volume_pressure, 6),
            "forecast": forecast,
            "signal_markers": [
                {
                    "symbol": frame.symbol,
                    "side": side,
                    "price": frame.prices[-1],
                    "confidence": round(confidence, 4),
                    "observed_at": frame.observed_at.isoformat(),
                }
            ],
        }

    @staticmethod
    def _std(values: list[float]) -> float:
        if not values:
            return 0.0
        mean = sum(values) / len(values)
        return math.sqrt(sum((value - mean) ** 2 for value in values) / len(values))


class MlSignalPipelineWorker:
    """Non-blocking advisory pipeline for AI overlays and signal markers."""

    def __init__(
        self,
        *,
        repository: AdvancedTradingStateRepository,
        source: MarketSignalSource | None = None,
        inference_engine: LocalMomentumInferenceEngine | None = None,
        interval_seconds: float = 5.0,
    ) -> None:
        self._repository = repository
        self._source = source or DeterministicMarketSignalSource()
        self._inference = inference_engine or LocalMomentumInferenceEngine()
        self._interval_seconds = max(float(interval_seconds), 0.1)
        self._task: asyncio.Task | None = None
        self._stopped = asyncio.Event()

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stopped.clear()
        self._task = asyncio.create_task(self.run_forever(), name="ml-signal-pipeline")

    async def stop(self) -> None:
        self._stopped.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def run_once(self) -> dict[str, object]:
        frame = await self._source.next_frame()
        signal = self._inference.infer(frame)
        payload = AiStrategyContextRequest(
            slug=f"ml-signal-{frame.symbol.lower()}",
            version="live-v1",
            display_name=f"ML Signal {frame.symbol}",
            model_family="local_momentum_inference",
            metrics={
                "confidence": signal["confidence"],
                "momentum": signal["momentum"],
                "volatility": signal["volatility"],
                "volume_pressure": signal["volume_pressure"],
            },
            risk_context={
                "advisory_only": True,
                "execution_mutation": False,
                "source": "ml_signal_pipeline",
            },
            signal_context={
                "symbol": frame.symbol,
                "side": signal["side"],
                "forecast": signal["forecast"],
                "signal_markers": signal["signal_markers"],
                "observed_at": frame.observed_at.isoformat(),
            },
        )
        return self._repository.upsert_ai_strategy_context(payload)

    async def run_forever(self) -> None:
        while not self._stopped.is_set():
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                # The advisory worker must never break app startup or execution.
                pass
            await asyncio.sleep(self._interval_seconds)
