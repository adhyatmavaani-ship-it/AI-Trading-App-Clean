from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.core.config import Settings
from app.services.strategy_controller import StrategyController


@dataclass
class StrategyOptimizerWorker:
    settings: Settings
    strategy_controller: StrategyController
    user_id: str = "system"

    def __post_init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        if not self.settings.strategy_optimizer_enabled:
            return
        if self._task is not None and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop(), name="strategy-optimizer")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            try:
                await self._task
            finally:
                self._task = None

    async def run_once(self) -> dict:
        return self.strategy_controller.adjust_weights(self.user_id)

    async def _run_loop(self) -> None:
        interval = max(float(self.settings.strategy_optimizer_interval_seconds), 30.0)
        while not self._stop_event.is_set():
            await self.run_once()
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                continue
