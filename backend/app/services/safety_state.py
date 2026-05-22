from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any

from app.core.config import Settings
from app.services.redis_cache import RedisCache

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SafetyComponent:
    name: str
    healthy: bool
    reason: str
    producer_last_seen_ts: str | None
    producer_age_ms: float | None
    metadata: dict[str, Any]

    def to_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "healthy": self.healthy,
            "reason": self.reason,
            "producer_last_seen_ts": self.producer_last_seen_ts,
            "producer_age_ms": self.producer_age_ms,
            "metadata": self.metadata,
        }


@dataclass
class SafetyStateService:
    settings: Settings
    cache: RedisCache
    store: Any | None = None

    def snapshot(self, *, trading_mode: str) -> dict[str, Any]:
        components = {
            "websocket": self.websocket_health(),
            "feed": self.feed_health(),
            "reconciliation": self.reconciliation_health(),
            "ai_latency": self.latency_health(
                name="ai_latency",
                primary_key="ai:latency",
                fallback_scalar_key="monitor:ai_worker_latency_ms",
                threshold_ms=float(self.settings.execution_ai_timeout_threshold_ms),
            ),
            "exchange_latency": self.latency_health(
                name="exchange_latency",
                primary_key="exchange:latency",
                fallback_scalar_key="monitor:exchange_latency_ms",
                fallback_scalar_key_alt="monitor:execution_latency_ms",
                threshold_ms=float(self.settings.execution_exchange_latency_threshold_ms),
            ),
        }
        reasons = [
            component.reason
            for component in components.values()
            if not component.healthy
        ]
        live_mode = str(trading_mode or "").lower() == "live"
        execution_available = not live_mode or not reasons
        return {
            "trading_mode": str(trading_mode or "paper").lower(),
            "execution_available": execution_available,
            "health_reason": "healthy" if execution_available else "; ".join(reasons),
            "components": {key: value.to_payload() for key, value in components.items()},
            "operational_metrics": self.operational_metrics(),
            "db_write_pressure": self.db_write_pressure(),
            "worker_heartbeats": self.worker_heartbeats(),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    def unhealthy_reasons(self, *, trading_mode: str) -> tuple[list[str], dict[str, Any]]:
        snapshot = self.snapshot(trading_mode=trading_mode)
        if snapshot["execution_available"]:
            return [], snapshot
        components = snapshot["components"]
        reasons = [
            str(component.get("reason"))
            for component in components.values()
            if not bool(component.get("healthy", False))
        ]
        self._log_unhealthy_once(reasons, snapshot)
        return reasons, snapshot

    def websocket_health(self) -> SafetyComponent:
        raw = self.cache.get("monitor:websocket_connected")
        last_seen = self._last_seen("monitor:websocket_connected:last_seen_ts")
        age_ms = self._age_ms(last_seen)
        metadata = {"connected": raw}
        if raw is None:
            return self._component("websocket", False, "websocket state missing", last_seen, age_ms, metadata)
        connected = str(raw).strip().lower() not in {"0", "false", "no", "disconnected", "offline"}
        if not connected:
            return self._component("websocket", False, "websocket disconnected", last_seen, age_ms, metadata)
        if self._is_stale(age_ms):
            return self._component("websocket", False, "websocket producer stale", last_seen, age_ms, metadata)
        return self._component("websocket", True, "healthy", last_seen, age_ms, metadata)

    def feed_health(self) -> SafetyComponent:
        payload = self.cache.get_json("market:feed:health") or {}
        last_seen = self._payload_last_seen(payload, "producer_last_seen_ts", "checked_at")
        age_ms = self._age_ms(last_seen)
        if not payload:
            return self._component("feed", False, "market feed health missing", last_seen, age_ms, {})
        if self._is_stale(age_ms):
            return self._component("feed", False, "market feed producer stale", last_seen, age_ms, payload)
        if not bool(payload.get("healthy", False)):
            reason = str(payload.get("health_reason") or ", ".join(payload.get("reasons") or []) or "market feed unhealthy")
            return self._component("feed", False, reason, last_seen, age_ms, payload)
        return self._component("feed", True, "healthy", last_seen, age_ms, payload)

    def reconciliation_health(self) -> SafetyComponent:
        payload = self.cache.get_json("broker:reconciliation:last") or {}
        last_seen = self._payload_last_seen(payload, "producer_last_seen_ts", "checked_at")
        age_ms = self._age_ms(last_seen)
        max_age_ms = max(
            float(self.settings.state_heartbeat_max_age_ms),
            float(self.settings.broker_reconciliation_interval_seconds) * 2_000.0,
        )
        if not payload:
            return self._component("reconciliation", False, "broker reconciliation missing", last_seen, age_ms, {})
        if self._is_stale(age_ms, max_age_ms=max_age_ms):
            return self._component("reconciliation", False, "broker reconciliation producer stale", last_seen, age_ms, payload)
        mismatch_count = int(payload.get("mismatch_count", 0) or 0)
        duplicate_ack_count = int(payload.get("duplicate_ack_count", 0) or 0)
        if mismatch_count > 0:
            return self._component("reconciliation", False, "broker reconciliation mismatch", last_seen, age_ms, payload)
        if duplicate_ack_count > 0:
            return self._component("reconciliation", False, "duplicate broker acknowledgement", last_seen, age_ms, payload)
        return self._component("reconciliation", True, "healthy", last_seen, age_ms, payload)

    def latency_health(
        self,
        *,
        name: str,
        primary_key: str,
        fallback_scalar_key: str,
        threshold_ms: float,
        fallback_scalar_key_alt: str | None = None,
    ) -> SafetyComponent:
        payload = self.cache.get_json(primary_key) or {}
        scalar_key = fallback_scalar_key
        latency_ms = self._payload_float(payload, "latency_ms")
        if latency_ms is None:
            latency_ms = self._float_key(fallback_scalar_key)
        if latency_ms is None and fallback_scalar_key_alt is not None:
            scalar_key = fallback_scalar_key_alt
            latency_ms = self._float_key(fallback_scalar_key_alt)
        last_seen = self._payload_last_seen(payload, "producer_last_seen_ts", "checked_at")
        if last_seen is None:
            last_seen = self._last_seen(f"{scalar_key}:last_seen_ts")
        age_ms = self._age_ms(last_seen)
        metadata = {**payload, "latency_ms": latency_ms}
        if latency_ms is None:
            return self._component(name, False, f"{name} missing", last_seen, age_ms, metadata)
        if self._is_stale(age_ms):
            return self._component(name, False, f"{name} producer stale", last_seen, age_ms, metadata)
        if float(latency_ms) > threshold_ms:
            return self._component(name, False, f"{name} too high", last_seen, age_ms, metadata)
        return self._component(name, True, "healthy", last_seen, age_ms, metadata)

    def operational_metrics(self) -> dict[str, Any]:
        return {
            "execution_circuit_breaker_open_total": self._int_key("monitor:execution_circuit_breaker_open_total"),
            "websocket_reconnect_total": self._int_key("monitor:websocket_reconnect_count"),
            "stale_feed_detection_total": self._int_key("monitor:websocket_stale_feed_count"),
            "duplicate_execution_prevention_total": self._int_key("monitor:duplicate_execution_prevented"),
            "orphan_execution_detection_total": self._int_key("monitor:execution_orphan_detected_count"),
            "reconciliation_mismatch_total": self._int_key("monitor:broker_reconciliation_mismatch_count"),
            "broker_duplicate_ack_total": self._int_key("monitor:broker_duplicate_ack_count"),
            "execution_latency_ms": self._float_key("monitor:execution_latency_ms"),
            "broker_latency_ms": self._float_key("monitor:exchange_latency_ms"),
            "last_circuit_block": self.cache.get_json("execution:circuit:last_block") or {},
            "startup_recovery": self.cache.get_json("execution:recovery:startup") or {},
        }

    def db_write_pressure(self) -> dict[str, Any]:
        if self.store is None or not hasattr(self.store, "db_write_pressure"):
            return {"available": False}
        pressure = dict(self.store.db_write_pressure())
        pressure["available"] = True
        pressure["db_lock_contention_total"] = int(pressure.get("lock_contention", 0) or 0)
        pressure["db_retry_total"] = int(pressure.get("retry_count", 0) or 0)
        pressure["db_slow_transaction_total"] = int(pressure.get("slow_transactions", 0) or 0)
        return pressure

    def worker_heartbeats(self) -> dict[str, Any]:
        heartbeats: dict[str, Any] = {}
        for key in self.cache.keys("worker:*:heartbeat"):
            last_seen = self._last_seen(key)
            heartbeats[key] = {
                "producer_last_seen_ts": last_seen,
                "producer_age_ms": self._age_ms(last_seen),
                "healthy": not self._is_stale(self._age_ms(last_seen)),
            }
        return heartbeats

    def _component(
        self,
        name: str,
        healthy: bool,
        reason: str,
        last_seen: str | None,
        age_ms: float | None,
        metadata: dict[str, Any],
    ) -> SafetyComponent:
        return SafetyComponent(
            name=name,
            healthy=healthy,
            reason=reason,
            producer_last_seen_ts=last_seen,
            producer_age_ms=round(age_ms, 4) if age_ms is not None else None,
            metadata=metadata,
        )

    def _log_unhealthy_once(self, reasons: list[str], snapshot: dict[str, Any]) -> None:
        signature = "|".join(sorted(reasons)) or "unknown"
        log_key = f"safety:state:log:{abs(hash(signature))}"
        if not self.cache.set_if_absent(log_key, "1", ttl=30):
            return
        logger.warning(
            "safety_state_unhealthy",
            extra={
                "event": "safety_state_unhealthy",
                "context": {
                    "reasons": reasons,
                    "execution_available": snapshot.get("execution_available"),
                    "components": snapshot.get("components"),
                },
            },
        )

    def _is_stale(self, age_ms: float | None, *, max_age_ms: float | None = None) -> bool:
        if age_ms is None:
            return True
        return age_ms > float(max_age_ms or self.settings.state_heartbeat_max_age_ms)

    def _payload_last_seen(self, payload: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            raw = payload.get(key)
            parsed = self._parse_timestamp(raw)
            if parsed is not None:
                return parsed.isoformat()
        return None

    def _last_seen(self, key: str) -> str | None:
        parsed = self._parse_timestamp(self.cache.get(key))
        return parsed.isoformat() if parsed is not None else None

    def _parse_timestamp(self, raw: Any) -> datetime | None:
        if raw is None:
            return None
        try:
            if isinstance(raw, (int, float)) or str(raw).replace(".", "", 1).isdigit():
                value = float(raw)
                if value > 10_000_000_000:
                    value = value / 1000.0
                return datetime.fromtimestamp(value, tz=timezone.utc)
            parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError, OSError):
            return None

    def _age_ms(self, last_seen: str | None) -> float | None:
        parsed = self._parse_timestamp(last_seen)
        if parsed is None:
            return None
        return max(0.0, (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds() * 1000.0)

    def _float_key(self, key: str) -> float | None:
        raw = self.cache.get(key)
        if raw is None:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    def _int_key(self, key: str) -> int:
        raw = self.cache.get(key)
        try:
            return int(raw or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _payload_float(payload: dict[str, Any], key: str) -> float | None:
        try:
            return float(payload[key])
        except (KeyError, TypeError, ValueError):
            return None
