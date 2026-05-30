from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging

from app.services.event_dispatcher import EventDispatcher

logger = logging.getLogger(__name__)


@dataclass
class EventDispatcherWorker:
    dispatcher: EventDispatcher
    interval_seconds: float = 2.0
    enabled: bool = True

    def __post_init__(self) -> None:
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if not self.enabled:
            return
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run_loop(), name="execution-event-dispatcher")

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
        interval = max(float(self.interval_seconds), 0.25)
        while True:
            try:
                await asyncio.to_thread(self.dispatcher.dispatch_once)
            except Exception as exc:  # pragma: no cover
                logger.exception(
                    "execution_event_dispatcher_failed",
                    extra={
                        "event": "execution_event_dispatcher_failed",
                        "context": {"error": str(exc)[:200]},
                    },
                )
            await asyncio.sleep(interval)
