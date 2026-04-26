from __future__ import annotations

import asyncio
import functools
import logging
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from app.core.config import Settings
from app.services.redis_cache import RedisCache

logger = logging.getLogger(__name__)


@dataclass
class LatencyMonitor:
    settings: Settings
    cache: RedisCache

    async def timed_call(
        self,
        name: str,
        primary: Callable[[], Awaitable[Any]],
        fallback: Callable[[], Awaitable[Any]] | None = None,
    ) -> Any:
        started = time.perf_counter()
        try:
            result = await primary()
            elapsed_ms = (time.perf_counter() - started) * 1000
            self._record(name, elapsed_ms, used_fallback=False)
            if elapsed_ms > self.settings.latency_spike_threshold_ms and fallback is not None:
                logger.warning(
                    "latency_spike_detected",
                    extra={"event": "latency_spike_detected", "context": {"name": name, "latency_ms": elapsed_ms}},
                )
            return result
        except Exception:
            elapsed_ms = (time.perf_counter() - started) * 1000
            self._record(name, elapsed_ms, used_fallback=False)
            if fallback is None:
                raise
        started = time.perf_counter()
        result = await fallback()
        elapsed_ms = (time.perf_counter() - started) * 1000
        self._record(name, elapsed_ms, used_fallback=True)
        return result

    def record_sync(self, name: str, elapsed_ms: float, used_fallback: bool = False) -> None:
        self._record(name, elapsed_ms, used_fallback)

    def instrument(self, name: str):
        def decorator(fn):
            if asyncio.iscoroutinefunction(fn):
                @functools.wraps(fn)
                async def async_wrapper(*args, **kwargs):
                    started = time.perf_counter()
                    try:
                        return await fn(*args, **kwargs)
                    finally:
                        self._record(name, (time.perf_counter() - started) * 1000, used_fallback=False)
                return async_wrapper

            @functools.wraps(fn)
            def sync_wrapper(*args, **kwargs):
                started = time.perf_counter()
                try:
                    return fn(*args, **kwargs)
                finally:
                    self._record(name, (time.perf_counter() - started) * 1000, used_fallback=False)
            return sync_wrapper
        return decorator

    def degraded_mode(self) -> bool:
        state = self.cache.get_json("latency:state") or {}
        return bool(state.get("degraded_mode", False))

    def _record(self, name: str, elapsed_ms: float, used_fallback: bool) -> None:
        key = f"latency:{name}"
        state = self.cache.get_json(key) or {"samples": [], "fallbacks": 0}
        samples = list(state.get("samples", []))[-99:]
        samples.append(elapsed_ms)
        fallbacks = int(state.get("fallbacks", 0)) + int(used_fallback)
        self.cache.set_json(key, {"samples": samples, "fallbacks": fallbacks}, ttl=self.settings.monitor_state_ttl_seconds)
        degraded = elapsed_ms > self.settings.latency_spike_threshold_ms
        self.cache.set_json(
            "latency:state",
            {"degraded_mode": degraded, "last_name": name, "last_latency_ms": elapsed_ms, "used_fallback": used_fallback},
            ttl=self.settings.monitor_state_ttl_seconds,
        )
