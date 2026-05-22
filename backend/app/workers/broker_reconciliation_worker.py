from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from app.core.config import Settings
from app.services.broker_reconciliation import BrokerReconciliationEngine

logger = logging.getLogger(__name__)


@dataclass
class BrokerReconciliationWorker:
    settings: Settings
    reconciliation_engine: BrokerReconciliationEngine

    def __post_init__(self) -> None:
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if not self.settings.broker_reconciliation_enabled or self.settings.trading_mode != "live":
            return
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run_loop(), name="broker-reconciliation")

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
        interval = max(float(self.settings.broker_reconciliation_interval_seconds), 30.0)
        while True:
            try:
                await asyncio.to_thread(self.reconciliation_engine.reconcile_once)
                await asyncio.to_thread(self.reconciliation_engine.emergency_close_if_feed_frozen)
            except Exception as exc:  # pragma: no cover
                logger.exception("broker_reconciliation_failed", extra={"event": "broker_reconciliation_failed", "context": {"error": str(exc)[:200]}})
            await asyncio.sleep(interval)
