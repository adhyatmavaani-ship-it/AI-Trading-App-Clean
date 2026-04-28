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

    while True:
        result = container.retrain_trigger_service.run_if_needed()
        if result.get("trained"):
            logger.info("trade_probability_retraining_succeeded", extra=result)
        else:
            logger.warning("trade_probability_retraining_skipped", extra=result)
        time.sleep(cadence_seconds)
