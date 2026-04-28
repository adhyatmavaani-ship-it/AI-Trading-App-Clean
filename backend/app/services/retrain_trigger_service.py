from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.core.config import Settings


@dataclass
class RetrainTriggerService:
    settings: Settings
    cache: object
    trade_probability_engine: object

    last_trained_key: str = "ml:trade_probability:last_trained_at"
    last_processed_key: str = "ml:trade_probability:last_processed_sample_at"
    notification_key: str = "ml:trade_probability:last_update_notice"
    trigger_status_key: str = "ml:trade_probability:last_trigger_status"
    freeze_key: str = "ml:trade_probability:freeze"
    rollback_cooldown_key: str = "ml:trade_probability:rollback_cooldown_until"

    def evaluate(self, samples: list[dict] | None = None) -> dict:
        guard_state = self.guard_state()
        if guard_state["freeze_enabled"]:
            status = {
                "should_retrain": False,
                "reason": "learning_frozen",
                "trigger_mode": "frozen",
                "recent_trade_count": 0,
                "recent_win_rate": 0.0,
                "recent_win_rate_floor": float(self.settings.retrain_emergency_win_rate_floor),
                "new_closed_samples": 0,
                "batch_threshold": int(self.settings.retrain_batch_size),
                "last_trained_at": self.cache.get(self.last_trained_key),
                "last_processed_sample_at": self.cache.get(self.last_processed_key),
                **guard_state,
            }
            self.cache.set_json(self.trigger_status_key, status, ttl=self.settings.monitor_state_ttl_seconds)
            return status
        if guard_state["rollback_cooldown_active"]:
            status = {
                "should_retrain": False,
                "reason": "manual_rollback_cooldown",
                "trigger_mode": "cooldown",
                "recent_trade_count": 0,
                "recent_win_rate": 0.0,
                "recent_win_rate_floor": float(self.settings.retrain_emergency_win_rate_floor),
                "new_closed_samples": 0,
                "batch_threshold": int(self.settings.retrain_batch_size),
                "last_trained_at": self.cache.get(self.last_trained_key),
                "last_processed_sample_at": self.cache.get(self.last_processed_key),
                **guard_state,
            }
            self.cache.set_json(self.trigger_status_key, status, ttl=self.settings.monitor_state_ttl_seconds)
            return status
        rows = list(samples) if samples is not None else list(self.trade_probability_engine._load_samples())
        closed = [row for row in rows if row.get("outcome") is not None]
        closed.sort(key=lambda item: self._sample_timestamp(item) or datetime.min.replace(tzinfo=timezone.utc))
        recent_window = max(int(self.settings.retrain_recent_trade_window), 1)
        recent = closed[-recent_window:]
        recent_wins = sum(int(float(item.get("outcome", 0.0) or 0.0) > 0.0) for item in recent)
        recent_win_rate = recent_wins / max(len(recent), 1)
        last_processed_at = self._cache_timestamp(self.last_processed_key)
        new_closed = [
            row for row in closed
            if (self._sample_timestamp(row) or datetime.min.replace(tzinfo=timezone.utc)) > last_processed_at
        ]
        emergency_triggered = (
            len(recent) >= recent_window
            and recent_win_rate < float(self.settings.retrain_emergency_win_rate_floor)
        )
        batch_triggered = len(new_closed) >= max(int(self.settings.retrain_batch_size), 1)
        should_retrain = emergency_triggered or batch_triggered
        reason = "none"
        trigger_mode = "idle"
        if emergency_triggered:
            reason = "recent_win_rate_breach"
            trigger_mode = "emergency"
        elif batch_triggered:
            reason = "batch_size_reached"
            trigger_mode = "batch"
        status = {
            "should_retrain": should_retrain,
            "reason": reason,
            "trigger_mode": trigger_mode,
            "recent_trade_count": len(recent),
            "recent_win_rate": round(recent_win_rate, 6),
            "recent_win_rate_floor": float(self.settings.retrain_emergency_win_rate_floor),
            "new_closed_samples": len(new_closed),
            "batch_threshold": int(self.settings.retrain_batch_size),
            "last_trained_at": self.cache.get(self.last_trained_key),
            "last_processed_sample_at": self.cache.get(self.last_processed_key),
            **guard_state,
        }
        self.cache.set_json(
            self.trigger_status_key,
            status,
            ttl=self.settings.monitor_state_ttl_seconds,
        )
        return status

    def run_if_needed(self) -> dict:
        samples = list(self.trade_probability_engine._load_samples())
        evaluation = self.evaluate(samples=samples)
        if not evaluation["should_retrain"]:
            return {
                "trained": False,
                "reason": "trigger_not_met",
                "trigger": evaluation,
            }
        result = self.trade_probability_engine.train(
            samples=samples,
            recent_validation_window=int(self.settings.retrain_recent_validation_trades),
            min_recent_accuracy_lift=float(self.settings.retrain_min_accuracy_lift),
        )
        if result.get("trained"):
            performance = dict(result.get("performance") or {})
            performance["trigger_mode"] = evaluation.get("trigger_mode")
            result["performance"] = performance
            registry = getattr(self.trade_probability_engine, "registry", None)
            if registry is not None and hasattr(registry, "annotate_latest_probability_promotion"):
                registry.annotate_latest_probability_promotion(
                    trigger_mode=str(evaluation.get("trigger_mode", "") or "scheduled")
                )
            closed = [row for row in samples if row.get("outcome") is not None]
            latest_timestamp = max(
                (self._sample_timestamp(row) for row in closed),
                default=None,
            )
            now = datetime.now(timezone.utc)
            self.cache.set(
                self.last_trained_key,
                now.isoformat(),
                ttl=self.settings.monitor_state_ttl_seconds,
            )
            if latest_timestamp is not None:
                self.cache.set(
                    self.last_processed_key,
                    latest_timestamp.isoformat(),
                    ttl=self.settings.monitor_state_ttl_seconds,
                )
            self.cache.set_json(
                self.notification_key,
                {
                    "message": "AI just updated its strategy based on recent market moves.",
                    "model_version": result.get("model_version"),
                    "trigger_mode": evaluation.get("trigger_mode"),
                    "updated_at": now.isoformat(),
                },
                ttl=self.settings.monitor_state_ttl_seconds,
            )
        return {
            **result,
            "trigger": evaluation,
        }

    def set_freeze(
        self,
        *,
        enabled: bool,
        actor_user_id: str,
        reason: str = "",
    ) -> dict:
        payload = {
            "enabled": bool(enabled),
            "actor_user_id": actor_user_id,
            "reason": reason or ("manual_admin_freeze" if enabled else "manual_admin_unfreeze"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.cache.set_json(self.freeze_key, payload, ttl=self.settings.monitor_state_ttl_seconds)
        return self.guard_state()

    def set_manual_rollback_cooldown(
        self,
        *,
        actor_user_id: str,
        hours: int | None = None,
    ) -> dict:
        cooldown_hours = max(int(hours or self.settings.retrain_manual_rollback_cooldown_hours), 1)
        until = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=cooldown_hours)
        self.cache.set_json(
            self.rollback_cooldown_key,
            {
                "until": until.isoformat(),
                "actor_user_id": actor_user_id,
                "hours": cooldown_hours,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            ttl=max(cooldown_hours * 3600, self.settings.monitor_state_ttl_seconds),
        )
        return self.guard_state()

    def clear_manual_rollback_cooldown(self) -> dict:
        self.cache.set_json(
            self.rollback_cooldown_key,
            {
                "until": None,
                "actor_user_id": None,
                "hours": 0,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            ttl=self.settings.monitor_state_ttl_seconds,
        )
        return self.guard_state()

    def guard_state(self) -> dict:
        freeze_payload = self.cache.get_json(self.freeze_key) or {}
        rollback_payload = self.cache.get_json(self.rollback_cooldown_key) or {}
        rollback_until = self._parse_timestamp(rollback_payload.get("until"))
        now = datetime.now(timezone.utc)
        return {
            "freeze_enabled": bool(freeze_payload.get("enabled", False)),
            "freeze_reason": str(freeze_payload.get("reason", "") or ""),
            "freeze_updated_at": freeze_payload.get("updated_at"),
            "rollback_cooldown_until": rollback_payload.get("until"),
            "rollback_cooldown_active": rollback_until is not None and rollback_until > now,
            "rollback_cooldown_hours": int(rollback_payload.get("hours", 0) or 0),
        }

    def _cache_timestamp(self, key: str) -> datetime:
        raw = self.cache.get(key)
        if not raw:
            return datetime.min.replace(tzinfo=timezone.utc)
        return self._parse_timestamp(raw) or datetime.min.replace(tzinfo=timezone.utc)

    def _sample_timestamp(self, sample: dict) -> datetime | None:
        raw = sample.get("closed_at") or sample.get("updated_at") or sample.get("created_at")
        return self._parse_timestamp(raw)

    def _parse_timestamp(self, raw) -> datetime | None:
        if raw is None:
            return None
        if isinstance(raw, datetime):
            return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
        if isinstance(raw, str):
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        if hasattr(raw, "to_datetime"):
            parsed = raw.to_datetime()
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        return None
