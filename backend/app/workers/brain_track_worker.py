from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.services.container import get_container


async def run_brain_track_worker() -> None:
    container = get_container()
    tasks = [
        asyncio.create_task(container.dual_track_coordinator.run_brain_loop(symbol))
        for symbol in container.settings.websocket_symbols
    ]
    tasks.append(asyncio.create_task(run_self_healing_scheduler(container)))
    await asyncio.gather(*tasks)


async def run_self_healing_scheduler(container) -> None:
    last_run_date = None
    while True:
        utc_now = datetime.now(timezone.utc)
        target_hit = (
            utc_now.hour == container.settings.self_heal_evening_hour_utc
            and utc_now.minute >= container.settings.self_heal_evening_minute_utc
        )
        current_date = utc_now.date().isoformat()
        if target_hit and current_date != last_run_date:
            container.self_healing_service.nightly_sniper_threshold_tuning()
            last_run_date = current_date
        await asyncio.sleep(30)


def run() -> None:
    asyncio.run(run_brain_track_worker())

