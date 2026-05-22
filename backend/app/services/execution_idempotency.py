from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import logging
from typing import Any
from uuid import uuid4

from app.core.config import Settings
from app.core.exceptions import StateError
from app.schemas.trading import TradeRequest, TradeResponse
from app.services.redis_cache import RedisCache

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IdempotencyClaim:
    request: TradeRequest
    execution_request_id: str
    execution_attempt: int
    execution_origin: str
    replay_response: TradeResponse | None = None


@dataclass
class ExecutionIdempotencyService:
    settings: Settings
    cache: RedisCache
    store: Any | None = None

    def peek_replay(
        self,
        request: TradeRequest,
        *,
        idempotency_key: str | None,
        origin: str,
    ) -> IdempotencyClaim:
        execution_request_id = self.execution_request_id(request, idempotency_key=idempotency_key)
        response = self._cached_response(execution_request_id)
        if response is None:
            response = self._stored_response(execution_request_id)
        return IdempotencyClaim(
            request=self._request_with_signal_id(request, execution_request_id),
            execution_request_id=execution_request_id,
            execution_attempt=self._attempt_count(execution_request_id) + 1,
            execution_origin=origin,
            replay_response=response,
        )

    def claim(
        self,
        request: TradeRequest,
        *,
        idempotency_key: str | None,
        origin: str,
        trading_mode: str,
    ) -> IdempotencyClaim:
        execution_request_id = self.execution_request_id(request, idempotency_key=idempotency_key)
        replay = self._cached_response(execution_request_id)
        if replay is None:
            replay = self._stored_response(execution_request_id)
        attempt = self._increment_attempt(execution_request_id)
        prepared_request = self._request_with_signal_id(request, execution_request_id)
        if replay is not None:
            self._record_duplicate(execution_request_id, origin, replay=True)
            return IdempotencyClaim(prepared_request, execution_request_id, attempt, origin, replay)
        if str(trading_mode or "").lower() != "live":
            return IdempotencyClaim(prepared_request, execution_request_id, attempt, origin, None)

        stored = self._claim_stored_request(
            prepared_request,
            execution_request_id=execution_request_id,
            idempotency_key=idempotency_key,
            origin=origin,
        )
        if bool(stored.get("claimed", False)):
            self._audit(
                execution_request_id,
                "execution_requested",
                {
                    "origin": origin,
                    "attempt": int(stored.get("execution_attempt", attempt) or attempt),
                    "symbol": prepared_request.symbol.upper(),
                    "side": prepared_request.side.upper(),
                },
            )
        stored_response = self._response_from_row(stored)
        if stored_response is not None:
            self._record_duplicate(execution_request_id, origin, replay=True)
            return IdempotencyClaim(prepared_request, execution_request_id, int(stored.get("execution_attempt", attempt) or attempt), origin, stored_response)
        if not bool(stored.get("claimed", False)):
            status = str(stored.get("status", "") or "").upper()
            if status in {"REQUESTED", "VALIDATED", "SUBMITTED", "ACKNOWLEDGED", "UNKNOWN_AFTER_ERROR"}:
                self._record_duplicate(execution_request_id, origin, replay=False)
                raise StateError(
                    "Duplicate execution request is already in progress",
                    error_code="EXECUTION_IDEMPOTENCY_IN_PROGRESS",
                    details={
                        "execution_request_id": execution_request_id,
                        "execution_attempt": int(stored.get("execution_attempt", attempt) or attempt),
                        "execution_origin": origin,
                        "status": status,
                    },
                )
        attempt = int(stored.get("execution_attempt", attempt) or attempt)

        payload = {
            "execution_request_id": execution_request_id,
            "execution_attempt": attempt,
            "execution_origin": origin,
            "status": "IN_PROGRESS",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "symbol": request.symbol.upper(),
            "side": request.side.upper(),
        }
        claimed = self.cache.set_if_absent(
            self._claim_key(execution_request_id),
            json.dumps(payload),
            ttl=int(self.settings.execution_idempotency_ttl_seconds),
        )
        if not claimed:
            replay = self._cached_response(execution_request_id)
            if replay is not None:
                self._record_duplicate(execution_request_id, origin, replay=True)
                return IdempotencyClaim(prepared_request, execution_request_id, attempt, origin, replay)
            self._record_duplicate(execution_request_id, origin, replay=False)
            raise StateError(
                "Duplicate execution request is already in progress",
                error_code="EXECUTION_IDEMPOTENCY_IN_PROGRESS",
                details={
                    "execution_request_id": execution_request_id,
                    "execution_attempt": attempt,
                    "execution_origin": origin,
                },
            )
        self.cache.set_json(
            self._state_key(execution_request_id),
            payload,
            ttl=int(self.settings.execution_idempotency_ttl_seconds),
        )
        return IdempotencyClaim(prepared_request, execution_request_id, attempt, origin, None)

    def mark_validated(self, claim: IdempotencyClaim) -> None:
        if self.store is not None:
            self.store.update_execution_request_status(claim.execution_request_id, status="VALIDATED")
            self._audit(
                claim.execution_request_id,
                "validation_passed",
                {"origin": claim.execution_origin, "attempt": claim.execution_attempt},
            )

    def mark_submitted(self, claim: IdempotencyClaim) -> None:
        if self.store is not None:
            self.store.update_execution_request_status(claim.execution_request_id, status="SUBMITTED")
            self._audit(
                claim.execution_request_id,
                "broker_submit",
                {"origin": claim.execution_origin, "attempt": claim.execution_attempt},
            )

    def complete(self, claim: IdempotencyClaim, response: TradeResponse | dict[str, Any]) -> None:
        payload = response.model_dump() if hasattr(response, "model_dump") else dict(response)
        self.cache.set_json(
            self._response_key(claim.execution_request_id),
            payload,
            ttl=int(self.settings.execution_idempotency_ttl_seconds),
        )
        self.cache.set_json(
            self._state_key(claim.execution_request_id),
            {
                "execution_request_id": claim.execution_request_id,
                "execution_attempt": claim.execution_attempt,
                "execution_origin": claim.execution_origin,
                "status": "COMPLETED",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "trade_id": str(payload.get("trade_id", "")),
            },
            ttl=int(self.settings.execution_idempotency_ttl_seconds),
        )
        if self.store is not None:
            self.store.update_execution_request_status(
                claim.execution_request_id,
                status="FILLED",
                trade_id=str(payload.get("trade_id", "")),
                response=payload,
            )
            self._audit(
                claim.execution_request_id,
                "execution_resolved",
                {
                    "origin": claim.execution_origin,
                    "attempt": claim.execution_attempt,
                    "trade_id": str(payload.get("trade_id", "")),
                    "status": str(payload.get("status", "")),
                },
            )

    def mark_unknown_failure(self, claim: IdempotencyClaim, exc: Exception) -> None:
        self.cache.set_json(
            self._state_key(claim.execution_request_id),
            {
                "execution_request_id": claim.execution_request_id,
                "execution_attempt": claim.execution_attempt,
                "execution_origin": claim.execution_origin,
                "status": "UNKNOWN_AFTER_ERROR",
                "error": str(exc)[:200],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            ttl=int(self.settings.execution_idempotency_ttl_seconds),
        )
        if self.store is not None:
            self.store.update_execution_request_status(
                claim.execution_request_id,
                status="FAILED",
                error=str(exc)[:500],
            )
            self._audit(
                claim.execution_request_id,
                "validation_failed",
                {
                    "origin": claim.execution_origin,
                    "attempt": claim.execution_attempt,
                    "error": str(exc)[:300],
                },
            )

    def recover_orphan_requests(self) -> list[dict[str, Any]]:
        if self.store is None:
            return []
        return list(self.store.orphan_execution_requests())

    def execution_request_id(self, request: TradeRequest, *, idempotency_key: str | None) -> str:
        raw_key = str(idempotency_key or request.signal_id or "").strip()
        if raw_key:
            digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:24]
            return f"exec_{digest}"
        fingerprint = {
            "user_id": request.user_id,
            "symbol": request.symbol.upper(),
            "side": request.side.upper(),
            "quantity": request.quantity,
            "requested_notional": request.requested_notional,
            "order_type": request.order_type,
            "limit_price": request.limit_price,
            "confidence": round(float(request.confidence), 8),
            "reason": request.reason,
        }
        digest = hashlib.sha256(json.dumps(fingerprint, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:24]
        return f"exec_{digest}"

    def _claim_stored_request(
        self,
        request: TradeRequest,
        *,
        execution_request_id: str,
        idempotency_key: str | None,
        origin: str,
    ) -> dict[str, Any]:
        if self.store is None:
            return {"claimed": True, "execution_attempt": self._attempt_count(execution_request_id)}
        return self.store.claim_execution_request(
            execution_request_id=execution_request_id,
            idempotency_key_hash=self._idempotency_hash(idempotency_key or execution_request_id),
            request_payload=request.model_dump(mode="json"),
            execution_origin=origin,
        )

    def _request_with_signal_id(self, request: TradeRequest, execution_request_id: str) -> TradeRequest:
        if request.signal_id:
            return request
        return request.model_copy(update={"signal_id": execution_request_id})

    def _cached_response(self, execution_request_id: str) -> TradeResponse | None:
        payload = self.cache.get_json(self._response_key(execution_request_id))
        if not payload:
            payload = self.cache.get_json(f"signal:response:{execution_request_id}")
        if not payload:
            return None
        payload["duplicate_signal"] = True
        return TradeResponse(**payload)

    def _stored_response(self, execution_request_id: str) -> TradeResponse | None:
        if self.store is None:
            return None
        row = self.store.execution_request_by_id(execution_request_id)
        if not row:
            return None
        return self._response_from_row(row)

    def _response_from_row(self, row: dict[str, Any]) -> TradeResponse | None:
        payload = self._json_dict(row.get("response_json"))
        if not payload:
            return None
        payload["duplicate_signal"] = True
        return TradeResponse(**payload)

    def _increment_attempt(self, execution_request_id: str) -> int:
        return self.cache.increment(
            f"execution:idempotency:attempts:{execution_request_id}",
            ttl=int(self.settings.execution_idempotency_ttl_seconds),
        )

    def _attempt_count(self, execution_request_id: str) -> int:
        try:
            return int(self.cache.get(f"execution:idempotency:attempts:{execution_request_id}") or 0)
        except ValueError:
            return 0

    def _record_duplicate(self, execution_request_id: str, origin: str, *, replay: bool) -> None:
        self.cache.increment("monitor:duplicate_execution_prevented", ttl=int(self.settings.monitor_state_ttl_seconds))
        self._audit(
            execution_request_id,
            "duplicate_execution_prevented",
            {"origin": origin, "replay": replay},
        )
        logger.warning(
            "duplicate_execution_prevented",
            extra={
                "event": "duplicate_execution_prevented",
                "context": {
                    "execution_request_id": execution_request_id,
                    "execution_origin": origin,
                    "replay": replay,
                },
            },
        )

    def _audit(self, execution_request_id: str, event_type: str, payload: dict[str, Any]) -> None:
        if self.store is None:
            return
        try:
            self.store.append_execution_audit_event(execution_request_id, event_type, payload)
        except Exception:
            logger.warning(
                "execution_audit_write_failed",
                exc_info=True,
                extra={
                    "event": "execution_audit_write_failed",
                    "context": {"execution_request_id": execution_request_id, "event_type": event_type},
                },
            )

    @staticmethod
    def _idempotency_hash(value: str) -> str:
        return hashlib.sha256(str(value).encode("utf-8")).hexdigest()

    @staticmethod
    def _json_dict(value: object) -> dict[str, Any]:
        try:
            parsed = json.loads(str(value or "{}"))
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def new_origin(default: str = "api") -> str:
        return f"{default}:{uuid4().hex[:8]}"

    @staticmethod
    def _claim_key(execution_request_id: str) -> str:
        return f"execution:idempotency:claim:{execution_request_id}"

    @staticmethod
    def _state_key(execution_request_id: str) -> str:
        return f"execution:idempotency:state:{execution_request_id}"

    @staticmethod
    def _response_key(execution_request_id: str) -> str:
        return f"execution:idempotency:response:{execution_request_id}"
