from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any
from uuid import uuid4

from app.core.config import Settings
from app.services.broker_truth import broker_truth_confidence

logger = logging.getLogger(__name__)


@dataclass
class BrokerStateSyncService:
    settings: Settings
    execution_engine: Any
    cache: Any
    store: Any
    worker_id: str = ""

    def __post_init__(self) -> None:
        if not self.worker_id:
            self.worker_id = f"broker-state-sync:{uuid4().hex[:8]}"

    def sync_once(self) -> dict[str, Any]:
        self._heartbeat()
        if self.store is None:
            return {"refreshed": 0, "failed": 0, "skipped": 0, "reason": "store_unavailable"}
        candidates = self.store.unresolved_broker_truth_states(
            max_attempts=int(self.settings.broker_state_sync_max_attempts),
            limit=int(self.settings.broker_state_sync_batch_size),
        )
        result = {"refreshed": 0, "failed": 0, "skipped": 0, "partial": 0, "unresolved": 0}
        for state in candidates:
            execution_request_id = str(state.get("execution_request_id") or "")
            lease = None
            if execution_request_id:
                lease = self.store.acquire_execution_lease(
                    execution_request_id,
                    worker_id=self.worker_id,
                    lease_seconds=float(self.settings.broker_state_sync_lease_seconds),
                )
                if not bool(lease.get("acquired", False)):
                    result["skipped"] += 1
                    continue
            try:
                refreshed = self._refresh_state(state)
            except Exception as exc:
                result["failed"] += 1
                self.store.mark_broker_truth_sync_attempt(
                    client_order_id=str(state.get("client_order_id")),
                    success=False,
                    error=str(exc)[:500],
                )
                self._increment("monitor:broker_state_sync_failures")
                logger.warning(
                    "broker_state_sync_failed",
                    extra={
                        "event": "broker_state_sync_failed",
                        "context": {
                            "client_order_id": state.get("client_order_id"),
                            "execution_request_id": execution_request_id,
                            "error": str(exc)[:200],
                        },
                    },
                )
            else:
                result["refreshed"] += 1
                result["partial"] += 1 if bool(refreshed.get("partial_fill", False)) else 0
                result["unresolved"] += 1 if bool(refreshed.get("unresolved", False)) else 0
                self.store.mark_broker_truth_sync_attempt(
                    client_order_id=str(state.get("client_order_id")),
                    success=True,
                )
            finally:
                if lease and bool(lease.get("acquired", False)):
                    self.store.release_execution_lease(
                        execution_request_id,
                        worker_id=self.worker_id,
                        lease_version=int(lease.get("lease_version", 0) or 0),
                    )
        summary = self.store.broker_truth_summary()
        confidence = self.synchronization_confidence(summary)
        payload = {
            **result,
            "summary": summary,
            "confidence_score": confidence,
            "confidence": "HIGH" if confidence >= 0.85 else "MEDIUM" if confidence >= 0.6 else "LOW",
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        if hasattr(self.cache, "set_json"):
            self.cache.set_json("broker:state_sync:last", payload, ttl=int(self.settings.monitor_state_ttl_seconds))
        return payload

    def synchronization_confidence(self, summary: dict[str, Any]) -> float:
        unresolved = int(summary.get("unresolved", 0) or 0)
        partial = int(summary.get("partial", 0) or 0)
        sync_failed = int(summary.get("sync_failed", 0) or 0)
        stale = self._oldest_unresolved_stale(summary)
        return broker_truth_confidence(
            normalized_status="ACKNOWLEDGED" if unresolved else "FILLED",
            stale=stale,
            partial_fill=partial > 0,
            unresolved=unresolved > 0,
            has_broker_order_id=True,
            retry_exhausted=sync_failed > 0,
        )

    def _refresh_state(self, state: dict[str, Any]) -> dict[str, Any]:
        symbol = str(state.get("symbol") or "").upper()
        broker_order_id = str(state.get("broker_order_id") or "")
        if not symbol or not broker_order_id:
            raise RuntimeError("missing broker order reference")
        order_status = self.execution_engine.fetch_order_status(symbol=symbol, order_id=broker_order_id)
        refreshed = self.store.upsert_broker_truth_state(
            client_order_id=str(state.get("client_order_id") or order_status.get("clientOrderId") or ""),
            execution_request_id=str(state.get("execution_request_id") or ""),
            exchange=str(state.get("exchange") or order_status.get("exchange") or ""),
            symbol=symbol,
            side=str(state.get("side") or order_status.get("side") or ""),
            order_payload=order_status,
            source="broker_state_sync",
        )
        return refreshed

    def _heartbeat(self) -> None:
        if hasattr(self.cache, "set"):
            self.cache.set(
                "worker:broker_state_sync:heartbeat",
                datetime.now(timezone.utc).isoformat(),
                ttl=max(300, int(float(self.settings.broker_state_sync_interval_seconds) * 3)),
            )

    def _increment(self, key: str) -> None:
        if hasattr(self.cache, "increment"):
            self.cache.increment(key, ttl=int(self.settings.monitor_state_ttl_seconds))

    def _oldest_unresolved_stale(self, summary: dict[str, Any]) -> bool:
        raw = summary.get("oldest_unresolved_at")
        if not raw:
            return False
        try:
            parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            return True
        return (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds() > float(
            self.settings.broker_state_freshness_seconds
        )
