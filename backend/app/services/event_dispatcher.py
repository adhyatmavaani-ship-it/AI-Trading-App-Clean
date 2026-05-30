from __future__ import annotations

from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import datetime, timezone
import logging
import time
from typing import Any, Callable
from uuid import uuid4

from app.core import metrics
from app.services.execution_storage import OutboxEventStore

logger = logging.getLogger(__name__)

EventHook = Callable[[dict[str, Any]], None]


@dataclass
class EventDispatcher:
    store: OutboxEventStore
    cache: Any | None = None
    worker_id: str = field(default_factory=lambda: f"event-dispatcher:{uuid4().hex[:8]}")
    batch_size: int = 50
    max_attempts: int = 5
    lease_seconds: float = 60.0
    base_retry_delay_seconds: float = 1.0
    max_retry_delay_seconds: float = 60.0
    dispatch_timeout_seconds: float = 5.0
    stall_seconds: float = 120.0
    backlog_warning_threshold: int = 100
    backlog_critical_threshold: int = 1_000
    pause_cache_key: str = "execution:event_dispatcher:paused"
    heartbeat_cache_key: str = "worker:event_dispatcher:heartbeat"
    metrics_hooks: list[EventHook] = field(default_factory=list)
    notification_hooks: list[EventHook] = field(default_factory=list)
    websocket_hooks: list[EventHook] = field(default_factory=list)

    def dispatch_once(self) -> dict[str, int]:
        started = time.perf_counter()
        self._heartbeat()
        backlog_snapshot = self._publish_backlog_metrics()
        if self.is_paused():
            return {"claimed": 0, "delivered": 0, "failed": 0, "duplicates_prevented": 0, "paused": 1}
        pressure = self._pressure_status(backlog_snapshot)
        events = self.store.claim_outbox_events(
            worker_id=self.worker_id,
            limit=self.batch_size,
            max_attempts=self.max_attempts,
            lease_seconds=self.lease_seconds,
        )
        result = {"claimed": len(events), "delivered": 0, "failed": 0, "duplicates_prevented": 0, "backpressure": 1 if pressure["backpressure"] else 0}
        for event in events:
            try:
                self._dispatch_event(event)
            except Exception as exc:
                result["failed"] += 1
                self._record_retry(event, exc)
                continue
            delivered = self.store.mark_outbox_delivered(
                str(event["event_id"]),
                worker_id=self.worker_id,
                dispatch_checksum=str(event.get("dispatch_checksum") or ""),
            )
            if delivered:
                result["delivered"] += 1
                continue
            result["duplicates_prevented"] += 1
            self._increment_cache_metric("monitor:event_duplicate_dispatch_prevented")
            metrics.event_duplicate_dispatch_prevented.inc()
        self._publish_backlog_metrics()
        metrics.event_replay_latency.observe(max(0.0, time.perf_counter() - started))
        return result

    def pause(self, reason: str = "operator") -> None:
        if self.cache is not None and hasattr(self.cache, "set_json"):
            self.cache.set_json(
                self.pause_cache_key,
                {"paused": True, "reason": reason, "paused_at": datetime.now(timezone.utc).isoformat()},
                ttl=86400,
            )

    def resume(self) -> None:
        if self.cache is not None and hasattr(self.cache, "set_json"):
            self.cache.set_json(
                self.pause_cache_key,
                {"paused": False, "reason": "resumed", "resumed_at": datetime.now(timezone.utc).isoformat()},
                ttl=86400,
            )

    def is_paused(self) -> bool:
        if self.cache is None or not hasattr(self.cache, "get_json"):
            return False
        payload = self.cache.get_json(self.pause_cache_key) or {}
        return bool(payload.get("paused", False))

    def status(self) -> dict[str, Any]:
        snapshot = self.store.outbox_metrics()
        pressure = self._pressure_status(snapshot)
        heartbeat = self._last_heartbeat()
        age_seconds = None
        if heartbeat is not None:
            age_seconds = max(0.0, (datetime.now(timezone.utc) - heartbeat.astimezone(timezone.utc)).total_seconds())
        stalled = age_seconds is None or age_seconds > float(self.stall_seconds)
        return {
            "worker_id": self.worker_id,
            "paused": self.is_paused(),
            "stalled": stalled,
            "last_heartbeat_at": heartbeat.isoformat() if heartbeat is not None else None,
            "heartbeat_age_seconds": round(age_seconds, 4) if age_seconds is not None else None,
            "stall_threshold_seconds": float(self.stall_seconds),
            "pressure": pressure,
            "outbox": snapshot,
        }

    def _dispatch_event(self, event: dict[str, Any]) -> None:
        for hook in [*self.metrics_hooks, *self.notification_hooks, *self.websocket_hooks]:
            executor = ThreadPoolExecutor(max_workers=1)
            future = executor.submit(hook, dict(event))
            try:
                future.result(timeout=float(self.dispatch_timeout_seconds))
            except TimeoutError as exc:
                future.cancel()
                executor.shutdown(wait=False, cancel_futures=True)
                raise TimeoutError(f"dispatch hook timed out after {self.dispatch_timeout_seconds}s") from exc
            finally:
                if future.done():
                    executor.shutdown(wait=False, cancel_futures=True)

    def _record_retry(self, event: dict[str, Any], exc: Exception) -> None:
        attempts = int(event.get("delivery_attempts", 0) or 0)
        poison = attempts >= int(self.max_attempts)
        delay = min(float(self.max_retry_delay_seconds), float(self.base_retry_delay_seconds) * (2 ** max(0, attempts - 1)))
        self.store.mark_outbox_failed(
            str(event["event_id"]),
            worker_id=self.worker_id,
            error=str(exc)[:500],
            retry_delay_seconds=delay,
            max_attempts=self.max_attempts,
            poison=poison,
        )
        self._increment_cache_metric("monitor:event_dispatcher_retries")
        metrics.event_dispatcher_retries.labels(event_type=str(event.get("event_type", "unknown"))).inc()
        if poison:
            self._increment_cache_metric("monitor:event_dead_letters")
            metrics.execution_event_dead_letters.labels(event_type=str(event.get("event_type", "unknown"))).inc()
        logger.warning(
            "execution_event_dispatch_failed",
            extra={
                "event": "execution_event_dispatch_failed",
                "context": {
                    "event_id": event.get("event_id"),
                    "event_type": event.get("event_type"),
                    "attempts": attempts,
                    "retry_delay_seconds": delay,
                    "error": str(exc)[:200],
                },
            },
        )

    def _publish_backlog_metrics(self) -> dict[str, Any]:
        snapshot = self.store.outbox_metrics()
        pressure = self._pressure_status(snapshot)
        snapshot = {**snapshot, "severity": pressure["severity"], "backpressure": pressure["backpressure"]}
        metrics.event_backlog_size.set(float(snapshot.get("backlog_size", 0)))
        metrics.execution_dispatcher_lag_seconds.set(float(snapshot.get("dispatcher_lag_seconds", 0.0) or 0.0))
        metrics.execution_outbox_growth_rate.set(float(snapshot.get("growth_last_60s", 0) or 0))
        if self.cache is not None and hasattr(self.cache, "set_json"):
            self.cache.set_json("monitor:execution_event_outbox", snapshot, ttl=300)
            self.cache.set_json("monitor:event_dispatcher_status", self.status() if self._status_safe() else {}, ttl=300)
        return snapshot

    def _increment_cache_metric(self, key: str) -> None:
        if self.cache is None or not hasattr(self.cache, "increment"):
            return
        self.cache.increment(key, ttl=300)

    def _heartbeat(self) -> None:
        if self.cache is None or not hasattr(self.cache, "set"):
            return
        self.cache.set(self.heartbeat_cache_key, datetime.now(timezone.utc).isoformat(), ttl=max(300, int(self.stall_seconds * 2)))

    def _last_heartbeat(self) -> datetime | None:
        if self.cache is None or not hasattr(self.cache, "get"):
            return None
        raw = self.cache.get(self.heartbeat_cache_key)
        if raw is None:
            return None
        try:
            parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            return None

    def _pressure_status(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        backlog = int(snapshot.get("backlog_size", 0) or 0)
        lag_seconds = float(snapshot.get("dispatcher_lag_seconds", 0.0) or 0.0)
        dead_letters = int(snapshot.get("dead_letter", 0) or 0)
        severity = "OK"
        backpressure = False
        if dead_letters > 0 or backlog >= int(self.backlog_critical_threshold) or lag_seconds >= float(self.stall_seconds):
            severity = "CRITICAL"
            backpressure = True
        elif backlog >= int(self.backlog_warning_threshold) or lag_seconds >= max(10.0, float(self.stall_seconds) / 2):
            severity = "WARNING"
            backpressure = True
        return {
            "severity": severity,
            "backpressure": backpressure,
            "backlog_size": backlog,
            "dispatcher_lag_seconds": round(lag_seconds, 4),
            "warning_threshold": int(self.backlog_warning_threshold),
            "critical_threshold": int(self.backlog_critical_threshold),
        }

    def _status_safe(self) -> bool:
        return True
