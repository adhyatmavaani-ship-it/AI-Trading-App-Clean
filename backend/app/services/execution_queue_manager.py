from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import random
import time

from app.core.config import Settings
from app.services.redis_cache import RedisCache
from app.services.shard_manager import ShardManager


@dataclass
class ExecutionQueueManager:
    settings: Settings
    cache: RedisCache
    shard_manager: ShardManager

    def enqueue_signal(self, signal: dict, subscriptions: list[dict]) -> dict:
        queued = {"high": 0, "normal": 0, "delayed": 0}
        shards: set[int] = set()
        signal_id = str(signal.get("signal_id") or signal.get("symbol"))
        for subscription in subscriptions:
            user_id = str(subscription["user_id"])
            shard_id = self.shard_manager.shard_id(user_id)
            priority = self.shard_manager.queue_priority(signal, subscription)
            delay_ms = self._random_delay_ms(priority)
            job = {
                "signal_id": signal_id,
                "signal_version": signal.get("signal_version"),
                "symbol": signal.get("symbol"),
                "strategy": signal.get("strategy"),
                "user_id": user_id,
                "tier": subscription.get("tier", "free"),
                "balance": float(subscription.get("balance", 0.0)),
                "risk_profile": subscription.get("risk_profile", "moderate"),
                "priority": priority,
                "shard_id": shard_id,
                "scheduled_delay_ms": delay_ms,
                "queued_at": datetime.now(timezone.utc).isoformat(),
            }
            self.cache.zadd_json(
                self._queue_key(priority, shard_id),
                score=time.time() + delay_ms / 1000,
                value=job,
            )
            queued[priority] += 1
            shards.add(shard_id)
        return {
            "queued_total": sum(queued.values()),
            "queue_counts": queued,
            "shards": len(shards),
        }

    def dequeue_batch(self, shard_id: int, limit: int | None = None) -> list[dict]:
        batch_limit = limit or self.settings.execution_queue_batch_size
        now = time.time()
        jobs: list[dict] = []
        for priority in ("high", "normal", "delayed"):
            if len(jobs) >= batch_limit:
                break
            due = self.cache.zpop_due_json(
                self._queue_key(priority, shard_id),
                max_score=now,
                limit=batch_limit - len(jobs),
            )
            jobs.extend(due)
        return jobs

    def queue_depth(self) -> dict[str, int]:
        totals = {"high": 0, "normal": 0, "delayed": 0}
        for shard_id in range(max(self.settings.execution_shard_count, 1)):
            for priority in totals:
                totals[priority] += self.cache.zcard(self._queue_key(priority, shard_id))
        totals["total"] = sum(totals.values())
        return totals

    def throttle(self, scope: str) -> float:
        bucket = int(time.time())
        key = f"rate:{scope}:{bucket}"
        count = self.cache.increment(key, ttl=2)
        if count <= self.settings.execution_rate_limit_per_second:
            return 0.0
        overflow = count - self.settings.execution_rate_limit_per_second
        return min(1.5, 0.05 * overflow + random.uniform(0.01, 0.15))

    def _queue_key(self, priority: str, shard_id: int) -> str:
        return f"execution:queue:{priority}:{shard_id}"

    def _random_delay_ms(self, priority: str) -> int:
        if priority == "high":
            return random.randint(
                max(0, self.settings.randomized_execution_delay_min_ms // 4),
                max(self.settings.randomized_execution_delay_min_ms, 1),
            )
        if priority == "delayed":
            return random.randint(
                self.settings.delayed_queue_min_ms,
                max(self.settings.delayed_queue_max_ms, self.settings.delayed_queue_min_ms),
            )
        return random.randint(
            self.settings.randomized_execution_delay_min_ms,
            max(self.settings.randomized_execution_delay_max_ms, self.settings.randomized_execution_delay_min_ms),
        )

