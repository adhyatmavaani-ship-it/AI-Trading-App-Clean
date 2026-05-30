from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging

from app.core.config import Settings
from app.services.broker_state_sync import BrokerStateSyncService

logger = logging.getLogger(__name__)


@dataclass
class BrokerStateSyncWorker:
    settings: Settings
    sync_service: BrokerStateSyncService

    def __post_init__(self) -> None:
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if not self.settings.broker_state_sync_enabled or self.settings.trading_mode != "live":
            return
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run_loop(), name="broker-state-sync")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _run_loop(self) -> None:
        interval = max(float(self.settings.broker_state_sync_interval_seconds), 10.0)
        while True:
            try:
                await asyncio.to_thread(self.sync_service.sync_once)
            except Exception as exc:  # pragma: no cover
                logger.exception(
                    "broker_state_sync_worker_failed",
                    extra={"event": "broker_state_sync_worker_failed", "context": {"error": str(exc)[:200]}},
                )
            await asyncio.sleep(interval)
