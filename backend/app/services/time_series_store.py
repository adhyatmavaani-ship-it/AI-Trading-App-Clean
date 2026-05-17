from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.redis_cache import RedisCache


@dataclass(frozen=True)
class TimeSeriesWriteResult:
    namespace: str
    stream_id: str | None


class TimeSeriesStore:
    """Append-only time-series facade; Redis Streams now, ClickHouse/Timescale later."""

    def __init__(self, cache: RedisCache, *, prefix: str = "ts") -> None:
        self.cache = cache
        self.prefix = prefix

    def append(self, *, namespace: str, payload: dict[str, Any], max_len: int = 10_000) -> TimeSeriesWriteResult:
        stream = f"{self.prefix}:{namespace}"
        stream_id = self.cache.stream_add(stream, payload, max_len=max_len)
        return TimeSeriesWriteResult(namespace=namespace, stream_id=stream_id)

    def range(self, *, namespace: str, count: int = 500) -> list[dict[str, Any]]:
        return self.cache.stream_range(
            f"{self.prefix}:{namespace}",
            count=max(1, min(int(count), 5000)),
        )
