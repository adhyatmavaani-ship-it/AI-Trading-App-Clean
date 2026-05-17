from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from app.services.redis_cache import RedisCache


@dataclass
class EventBusPublishResult:
    channel: str
    stream: str
    stream_id: str | None
    published_subscribers: int


class DistributedEventBus:
    """Redis Streams + pub/sub bridge for horizontally scaled realtime events."""

    def __init__(self, cache: RedisCache, *, stream_prefix: str = "events", max_len: int = 2000):
        self.cache = cache
        self.stream_prefix = stream_prefix
        self.max_len = max(int(max_len), 100)

    def publish(
        self,
        *,
        channel: str,
        event_type: str,
        payload: dict[str, Any],
        partition_key: str = "system",
    ) -> EventBusPublishResult:
        event = {
            **payload,
            "event_type": event_type,
            "partition_key": str(partition_key or "system"),
            "event_bus_published_at": datetime.now(timezone.utc).isoformat(),
        }
        stream = f"{self.stream_prefix}:{event_type}:{self._partition(partition_key)}"
        stream_id = self.cache.stream_add(stream, event, max_len=self.max_len)
        subscribers = self.cache.publish(channel, json.dumps(event, default=str))
        self._increment_throughput(event_type)
        return EventBusPublishResult(
            channel=channel,
            stream=stream,
            stream_id=stream_id,
            published_subscribers=subscribers,
        )

    def replay(self, *, event_type: str, partition_key: str = "system", count: int = 100) -> list[dict[str, Any]]:
        stream = f"{self.stream_prefix}:{event_type}:{self._partition(partition_key)}"
        return self.cache.stream_range(stream, count=max(1, min(int(count), 500)))

    @staticmethod
    def _partition(value: str, partitions: int = 16) -> int:
        digest = hashlib.sha1(str(value or "system").encode("utf-8")).hexdigest()
        return int(digest[:8], 16) % partitions

    def _increment_throughput(self, event_type: str) -> None:
        normalized = str(event_type or "event").lower()
        group = "analytics"
        if "chart" in normalized or "trade" in normalized or "market" in normalized:
            group = "market"
        elif "ai" in normalized or "assistant" in normalized:
            group = "ai"
        self.cache.increment(f"monitor:event_bus_{group}_throughput", ttl=60)
