from __future__ import annotations

import logging
import time

from app.core.config import get_settings
from app.services.container import get_container

logger = logging.getLogger(__name__)


def run() -> None:
    settings = get_settings()
    container = get_container()
    cadence_seconds = max(int(settings.probability_training_frequency_hours * 3600), 3600)
    last_success_key = "ml:trade_probability:last_trained_at"

    while True:
        now = time.time()
        last_success_raw = container.cache.get(last_success_key)
        last_success = float(last_success_raw) if last_success_raw else 0.0
        if now - last_success < cadence_seconds:
            time.sleep(min(300, cadence_seconds))
            continue

        result = container.trade_probability_engine.train()
        if result.get("trained"):
            container.cache.set(
                last_success_key,
                str(now),
                ttl=max(cadence_seconds * 2, 7200),
            )
            logger.info("trade_probability_retraining_succeeded", extra=result)
        else:
            logger.warning("trade_probability_retraining_skipped", extra=result)
        time.sleep(cadence_seconds)
