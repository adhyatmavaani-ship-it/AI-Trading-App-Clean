from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging

from app.core.config import Settings
from app.services.execution_engine import ExecutionEngine
from app.services.redis_state_manager import RedisStateManager

logger = logging.getLogger(__name__)


@dataclass
class BrokerReconciliationEngine:
    settings: Settings
    execution_engine: ExecutionEngine
    redis_state_manager: RedisStateManager
    cache: any
    store: any = None

    def reconcile_once(self) -> dict:
        local_trades = self.redis_state_manager.restore_active_trades()
        broker_positions = self.execution_engine.fetch_live_positions()
        broker_by_symbol = {
            str(position.get("symbol", "") or "").upper(): position
            for position in broker_positions
            if str(position.get("symbol", "") or "").strip()
        }
        duplicate_acknowledgements = self._duplicate_broker_acknowledgements(broker_positions)
        mismatches: list[dict] = []
        for trade in local_trades:
            symbol = str(trade.get("symbol", "") or "").upper()
            if symbol and symbol not in broker_by_symbol:
                trade["status"] = "BROKER_CLOSED"
                trade["broker_sync_reason"] = "missing_on_broker"
                self.redis_state_manager.save_active_trade(str(trade.get("trade_id")), trade)
                mismatches.append({"symbol": symbol, "reason": "missing_on_broker"})
        checked_at = datetime.now(timezone.utc).isoformat()
        result = {
            "checked_at": checked_at,
            "producer_last_seen_ts": checked_at,
            "producer_age_ms": 0.0,
            "local_active": len(local_trades),
            "broker_active": len(broker_positions),
            "mismatch_count": len(mismatches),
            "mismatches": mismatches,
            "duplicate_ack_count": len(duplicate_acknowledgements),
            "duplicate_acknowledgements": duplicate_acknowledgements,
        }
        self.cache.set_json("broker:reconciliation:last", result, ttl=self.settings.monitor_state_ttl_seconds)
        if self.store is not None:
            self.store.save_reconciliation_snapshot(result)
            if mismatches:
                for mismatch in mismatches:
                    self._audit_reconciliation_mismatch(mismatch, result)
        if mismatches:
            self.cache.increment("monitor:broker_reconciliation_mismatch_count", ttl=self.settings.monitor_state_ttl_seconds)
        if duplicate_acknowledgements:
            self.cache.increment("monitor:broker_duplicate_ack_count", ttl=self.settings.monitor_state_ttl_seconds)
            logger.warning(
                "broker_duplicate_acknowledgement_detected",
                extra={
                    "event": "broker_duplicate_acknowledgement_detected",
                    "context": {"duplicates": duplicate_acknowledgements},
                },
            )
        return result

    def emergency_close_if_feed_frozen(self, *, now: datetime | None = None) -> dict:
        current = now or datetime.now(timezone.utc)
        last_seen_raw = self.cache.get("market:feed:last_seen_ts")
        if not last_seen_raw:
            return {"triggered": False, "reason": "no_feed_timestamp"}
        try:
            if str(last_seen_raw).replace(".", "", 1).isdigit():
                last_seen = datetime.fromtimestamp(float(last_seen_raw), tz=timezone.utc)
            else:
                last_seen = datetime.fromisoformat(str(last_seen_raw))
                if last_seen.tzinfo is None:
                    last_seen = last_seen.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError, OSError):
            return {"triggered": False, "reason": "invalid_feed_timestamp"}
        age_seconds = (current - last_seen.astimezone(timezone.utc)).total_seconds()
        if age_seconds <= float(self.settings.broker_emergency_feed_freeze_seconds):
            return {"triggered": False, "age_seconds": age_seconds}
        orders = self.execution_engine.close_all_reduce_only(reason="feed_freeze_gt_10s")
        result = {
            "triggered": True,
            "reason": "feed_freeze_gt_10s",
            "age_seconds": round(age_seconds, 3),
            "orders": orders,
            "closed_count": len(orders),
            "triggered_at": current.isoformat(),
        }
        self.cache.set_json("broker:emergency:last", result, ttl=self.settings.monitor_state_ttl_seconds)
        return result

    def startup_recovery_report(self) -> dict:
        stale_after_seconds = float(getattr(self.settings, "execution_recovery_stale_seconds", 300.0))
        orphan_requests = self.store.orphan_execution_requests() if self.store is not None else []
        latest_snapshot = self.store.latest_reconciliation_snapshot() if self.store is not None else None
        recovery_checks = self._classify_recovery_checks(orphan_requests, stale_after_seconds=stale_after_seconds)
        result = {
            "orphan_execution_count": len(orphan_requests),
            "orphan_executions": orphan_requests,
            "recovery_checks": recovery_checks,
            "latest_reconciliation": latest_snapshot,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "auto_close_performed": False,
            "recovery_policy": "read_only_verify_before_action",
        }
        self.cache.set_json("execution:recovery:startup", result, ttl=self.settings.monitor_state_ttl_seconds)
        if orphan_requests:
            self.cache.increment("monitor:execution_orphan_detected_count", ttl=self.settings.monitor_state_ttl_seconds)
            logger.warning(
                "execution_orphans_detected_on_startup",
                extra={
                    "event": "execution_orphans_detected_on_startup",
                    "context": {
                        "orphan_execution_count": len(orphan_requests),
                        "recovery_checks": recovery_checks,
                        "auto_close_performed": False,
                    },
                },
            )
        return result

    def _classify_recovery_checks(self, orphan_requests: list[dict], *, stale_after_seconds: float) -> list[dict]:
        if self.store is None:
            return []
        now = datetime.now(timezone.utc)
        checks: list[dict] = []
        for request in orphan_requests:
            execution_request_id = str(request.get("execution_request_id") or "")
            status = str(request.get("status") or "").upper()
            updated_at = self._parse_timestamp(request.get("updated_at"))
            age_seconds = None if updated_at is None else (now - updated_at.astimezone(timezone.utc)).total_seconds()
            acknowledgements = self.store.broker_acknowledgements_for_execution(execution_request_id)
            reasons: list[str] = []
            if status == "SUBMITTED" and not acknowledgements:
                reasons.append("submitted_unacknowledged")
            if status == "ACKNOWLEDGED":
                reasons.append("acknowledged_unresolved")
            if age_seconds is None or age_seconds >= stale_after_seconds:
                reasons.append("stale_inflight_execution")
            if not reasons:
                reasons.append("inflight_execution")
            reason = ",".join(reasons)
            updated = self.store.mark_execution_recovery_checked(
                execution_request_id,
                recovery_reason=reason,
            )
            payload = {
                "execution_request_id": execution_request_id,
                "status": status,
                "recovery_reason": reason,
                "age_seconds": round(age_seconds, 3) if age_seconds is not None else None,
                "broker_ack_count": len(acknowledgements),
                "recovery_attempts": int((updated or {}).get("recovery_attempts", request.get("recovery_attempts", 0)) or 0),
                "safe_action": "manual_reconcile_required",
            }
            self.store.append_execution_audit_event(execution_request_id, "recovery_triggered", payload)
            checks.append(payload)
        return checks

    def _audit_reconciliation_mismatch(self, mismatch: dict, result: dict) -> None:
        if self.store is None:
            return
        execution_request_id = str(mismatch.get("execution_request_id") or mismatch.get("trade_id") or "unknown")
        self.store.append_execution_audit_event(
            execution_request_id,
            "reconciliation_mismatch",
            {
                "mismatch": mismatch,
                "checked_at": result.get("checked_at"),
                "mismatch_count": result.get("mismatch_count"),
            },
        )

    def _duplicate_broker_acknowledgements(self, broker_positions: list[dict]) -> list[dict]:
        seen: dict[str, int] = {}
        for position in broker_positions:
            client_order_id = str(
                position.get("clientOrderId")
                or position.get("client_order_id")
                or position.get("client_order_id_tag")
                or ""
            ).strip()
            if not client_order_id:
                continue
            seen[client_order_id] = seen.get(client_order_id, 0) + 1
        return [
            {"client_order_id": client_order_id, "count": count}
            for client_order_id, count in seen.items()
            if count > 1
        ]

    @staticmethod
    def _parse_timestamp(raw: object) -> datetime | None:
        if raw is None:
            return None
        try:
            parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            return None
