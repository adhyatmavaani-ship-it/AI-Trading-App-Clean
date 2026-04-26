from __future__ import annotations

import fnmatch
import json
import logging
import threading
import time
from typing import Any

from redis import Redis


logger = logging.getLogger(__name__)
_REDIS_DISABLED_LOGGED = False


class _InMemoryPipeline:
    def __init__(self, client: "_InMemoryRedisClient"):
        self._client = client
        self._operations: list[tuple[str, tuple[Any, ...]]] = []

    def incr(self, key: str) -> "_InMemoryPipeline":
        self._operations.append(("incr", (key,)))
        return self

    def expire(self, key: str, ttl: int) -> "_InMemoryPipeline":
        self._operations.append(("expire", (key, ttl)))
        return self

    def setex(self, key: str, ttl: int, value: str) -> "_InMemoryPipeline":
        self._operations.append(("setex", (key, ttl, value)))
        return self

    def delete(self, key: str) -> "_InMemoryPipeline":
        self._operations.append(("delete", (key,)))
        return self

    def zrem(self, key: str, member: str) -> "_InMemoryPipeline":
        self._operations.append(("zrem", (key, member)))
        return self

    def execute(self) -> list[Any]:
        results: list[Any] = []
        for name, args in self._operations:
            method = getattr(self._client, name)
            results.append(method(*args))
        self._operations.clear()
        return results


class _InMemoryPubSub:
    def subscribe(self, *args, **kwargs) -> None:
        return None

    def get_message(self, timeout: float | None = None) -> None:
        if timeout:
            time.sleep(min(timeout, 0.1))
        return None

    def close(self) -> None:
        return None


class _InMemoryRedisClient:
    def __init__(self):
        self._lock = threading.RLock()
        self._kv: dict[str, tuple[str, float | None]] = {}
        self._zsets: dict[str, dict[str, float]] = {}

    def _purge_if_expired(self, key: str) -> None:
        entry = self._kv.get(key)
        if entry is None:
            return
        _, expires_at = entry
        if expires_at is not None and expires_at <= time.time():
            self._kv.pop(key, None)

    def get(self, key: str) -> str | None:
        with self._lock:
            self._purge_if_expired(key)
            entry = self._kv.get(key)
            return entry[0] if entry is not None else None

    def set(self, key: str, value: str, ex: int | None = None, nx: bool = False) -> bool:
        with self._lock:
            self._purge_if_expired(key)
            if nx and key in self._kv:
                return False
            expires_at = (time.time() + ex) if ex is not None else None
            self._kv[key] = (value, expires_at)
            return True

    def setex(self, key: str, ttl: int, value: str) -> bool:
        return self.set(key, value, ex=ttl)

    def delete(self, key: str) -> int:
        with self._lock:
            existed = key in self._kv or key in self._zsets
            self._kv.pop(key, None)
            self._zsets.pop(key, None)
            return 1 if existed else 0

    def incr(self, key: str) -> int:
        with self._lock:
            self._purge_if_expired(key)
            current = int(self._kv.get(key, ("0", None))[0])
            updated = current + 1
            _, expires_at = self._kv.get(key, ("0", None))
            self._kv[key] = (str(updated), expires_at)
            return updated

    def expire(self, key: str, ttl: int) -> int:
        with self._lock:
            self._purge_if_expired(key)
            if key not in self._kv:
                return 0
            value, _ = self._kv[key]
            self._kv[key] = (value, time.time() + ttl)
            return 1

    def pipeline(self, transaction: bool = True) -> _InMemoryPipeline:
        return _InMemoryPipeline(self)

    def eval(self, script: str, num_keys: int, key: str, expected_value: str) -> int:
        with self._lock:
            actual = self.get(key)
            if actual == expected_value:
                return self.delete(key)
            return 0

    def publish(self, channel: str, message: str) -> int:
        return 0

    def scan_iter(self, match: str | None = None):
        with self._lock:
            keys = list(self._kv.keys()) + list(self._zsets.keys())
        for key in keys:
            self._purge_if_expired(key)
            if match is None or fnmatch.fnmatch(key, match):
                yield key

    def zadd(self, key: str, mapping: dict[str, float]) -> int:
        with self._lock:
            bucket = self._zsets.setdefault(key, {})
            before = len(bucket)
            bucket.update(mapping)
            return len(bucket) - before

    def zrangebyscore(
        self,
        key: str,
        min: float,
        max: float,
        start: int = 0,
        num: int | None = None,
    ) -> list[str]:
        with self._lock:
            members = self._zsets.get(key, {})
            ordered = [
                member
                for member, score in sorted(members.items(), key=lambda item: (item[1], item[0]))
                if float(min) <= score <= float(max)
            ]
        if num is None:
            return ordered[start:]
        return ordered[start : start + num]

    def zrem(self, key: str, member: str) -> int:
        with self._lock:
            bucket = self._zsets.get(key, {})
            if member in bucket:
                del bucket[member]
                return 1
            return 0

    def zcard(self, key: str) -> int:
        with self._lock:
            return len(self._zsets.get(key, {}))

    def ping(self) -> bool:
        return True

    def pubsub(self, ignore_subscribe_messages: bool = True) -> _InMemoryPubSub:
        return _InMemoryPubSub()

    def close(self) -> None:
        return None


class RedisCache:
    def __init__(self, url: str):
        self.url = (url or "").strip()
        self._using_fallback = False
        self._redis_enabled = bool(self.url)
        self.client = self._build_client(self.url)

    def _build_client(self, url: str):
        normalized_url = (url or "").strip()
        if not normalized_url:
            self._using_fallback = True
            self._log_disabled_once()
            return _InMemoryRedisClient()
        try:
            client = Redis.from_url(normalized_url, decode_responses=True)
            client.ping()
            return client
        except Exception as exc:
            self._using_fallback = True
            logger.warning(
                "redis_unavailable_falling_back_to_memory",
                extra={
                    "event": "redis_unavailable_falling_back_to_memory",
                    "context": {
                        "redis_url": normalized_url,
                        "error": str(exc)[:200],
                    },
                },
            )
            return _InMemoryRedisClient()

    def _log_disabled_once(self) -> None:
        global _REDIS_DISABLED_LOGGED
        if _REDIS_DISABLED_LOGGED:
            return
        logger.info("Redis disabled, using in-memory mode")
        _REDIS_DISABLED_LOGGED = True

    @property
    def using_fallback(self) -> bool:
        return self._using_fallback

    @property
    def redis_enabled(self) -> bool:
        return self._redis_enabled

    def get_json(self, key: str) -> dict[str, Any] | None:
        raw = self.client.get(key)
        return json.loads(raw) if raw else None

    def set_json(self, key: str, value: dict[str, Any], ttl: int) -> None:
        self.client.setex(key, ttl, json.dumps(value))

    def increment(self, key: str, ttl: int) -> int:
        pipeline = self.client.pipeline()
        pipeline.incr(key)
        pipeline.expire(key, ttl)
        count, _ = pipeline.execute()
        return int(count)

    def get(self, key: str) -> str | None:
        return self.client.get(key)

    def set(self, key: str, value: str, ttl: int | None = None) -> None:
        if ttl is None:
            self.client.set(key, value)
        else:
            self.client.setex(key, ttl, value)

    def set_if_absent(self, key: str, value: str, ttl: int) -> bool:
        return bool(self.client.set(key, value, ex=ttl, nx=True))

    def delete(self, key: str) -> None:
        self.client.delete(key)

    def delete_if_value_matches(self, key: str, expected_value: str) -> bool:
        script = """
        if redis.call('get', KEYS[1]) == ARGV[1] then
            return redis.call('del', KEYS[1])
        end
        return 0
        """
        return bool(self.client.eval(script, 1, key, expected_value))

    def publish(self, channel: str, message: str) -> int:
        return int(self.client.publish(channel, message))

    def keys(self, pattern: str) -> list[str]:
        return list(self.client.scan_iter(match=pattern))

    def zadd_json(self, key: str, score: float, value: dict[str, Any]) -> None:
        self.client.zadd(key, {json.dumps(value): score})

    def zpop_due_json(self, key: str, max_score: float, limit: int = 100) -> list[dict[str, Any]]:
        members = self.client.zrangebyscore(key, min=0, max=max_score, start=0, num=limit)
        if not members:
            return []
        pipeline = self.client.pipeline()
        for member in members:
            pipeline.zrem(key, member)
        pipeline.execute()
        return [json.loads(member) for member in members]

    def zcard(self, key: str) -> int:
        return int(self.client.zcard(key))
