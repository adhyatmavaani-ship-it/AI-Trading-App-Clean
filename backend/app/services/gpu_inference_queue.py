from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import time
from typing import Any
from uuid import uuid4

from app.services.redis_cache import RedisCache


@dataclass(frozen=True)
class GPUInferenceJob:
    job_id: str
    model: str
    symbol: str
    priority: int
    payload: dict[str, Any]
    queued_at: str
    runtime: str = "onnx"


class GPUInferenceQueue:
    """Latency-aware GPU inference queue facade, CPU-safe until workers exist."""

    def __init__(self, cache: RedisCache, *, queue_key: str = "gpu:inference:queue") -> None:
        self.cache = cache
        self.queue_key = queue_key

    def enqueue(
        self,
        *,
        model: str,
        symbol: str,
        payload: dict[str, Any],
        priority: int = 5,
        runtime: str = "onnx",
    ) -> GPUInferenceJob:
        job = GPUInferenceJob(
            job_id=str(uuid4()),
            model=model,
            symbol=symbol.upper(),
            priority=max(0, min(int(priority), 10)),
            payload=dict(payload),
            queued_at=datetime.now(timezone.utc).isoformat(),
            runtime=runtime,
        )
        score = (time.time() * 1000) - (job.priority * 15)
        self.cache.zadd_json(self.queue_key, score, job.__dict__)
        return job

    def dequeue_batch(self, *, limit: int = 16) -> list[GPUInferenceJob]:
        rows = self.cache.zpop_due_json(
            self.queue_key,
            max_score=time.time() * 1000,
            limit=max(1, min(int(limit), 128)),
        )
        return [GPUInferenceJob(**row) for row in rows]

    def depth(self) -> int:
        return self.cache.zcard(self.queue_key)
