from __future__ import annotations

import logging

import httpx


logger = logging.getLogger(__name__)


class AlertingService:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def send(self, title: str, message: str, severity: str = "INFO") -> None:
        logger.warning(
            "alert_emitted",
            extra={
                "event": "alert_emitted",
                "context": {"title": title, "severity": severity},
            },
        )
        if not self.webhook_url:
            return
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                self.webhook_url,
                json={"title": title, "message": message, "severity": severity},
            )
