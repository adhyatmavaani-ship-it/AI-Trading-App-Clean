from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import time
from typing import Any
from uuid import uuid4

from app.services.redis_cache import RedisCache


@dataclass
class AIWorkerJob:
    job_id: str
    job_type: str
    symbol: str
    priority: int
    payload: dict[str, Any]
    queued_at: str
    attempts: int = 0


class AIWorkerQueue:
    """Retry-safe Redis-backed queue for heavy market-intelligence workloads."""

    def __init__(self, cache: RedisCache, *, queue_key: str = "ai:worker:queue") -> None:
        self.cache = cache
        self.queue_key = queue_key

    def enqueue(
        self,
        *,
        job_type: str,
        symbol: str,
        payload: dict[str, Any],
        priority: int = 5,
        delay_ms: int = 0,
    ) -> AIWorkerJob:
        now = datetime.now(timezone.utc)
        job = AIWorkerJob(
            job_id=str(uuid4()),
            job_type=str(job_type),
            symbol=str(symbol or "").upper(),
            priority=max(0, min(int(priority), 10)),
            payload=dict(payload),
            queued_at=now.isoformat(),
        )
        score = (time.time() * 1000) + max(0, int(delay_ms)) - (job.priority * 10)
        self.cache.zadd_json(self.queue_key, score, job.__dict__)
        return job

    def dequeue(self, *, limit: int = 25) -> list[AIWorkerJob]:
        rows = self.cache.zpop_due_json(
            self.queue_key,
            max_score=time.time() * 1000,
            limit=max(1, min(int(limit), 100)),
        )
        return [AIWorkerJob(**row) for row in rows]

    def depth(self) -> int:
        return self.cache.zcard(self.queue_key)
