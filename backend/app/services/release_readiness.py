from __future__ import annotations

from typing import Any


class ReleaseReadinessEngine:
    """Advisory release gate built from existing monitoring state."""

    def evaluate(
        self,
        *,
        slo: dict[str, Any],
        incident: dict[str, Any],
        replay_checkpoint: dict[str, Any],
        capacity: dict[str, Any],
        redis_fallback: bool,
    ) -> dict[str, Any]:
        blockers: list[dict[str, Any]] = []
        if redis_fallback:
            blockers.append({"code": "redis_fallback", "severity": "critical"})
        if str(slo.get("mode", "")).upper() in {"DEGRADED", "INCIDENT"}:
            blockers.append({"code": "slo_not_normal", "severity": "high"})
        if str(incident.get("status", "")).upper() == "OPEN":
            blockers.append({"code": "open_incident", "severity": "critical"})
        if replay_checkpoint.get("valid") is not True:
            blockers.append({"code": "missing_replay_checkpoint", "severity": "medium"})
        if capacity.get("scale_mode") == "SCALE_OUT":
            blockers.append({"code": "capacity_pressure", "severity": "medium"})

        critical = any(item["severity"] == "critical" for item in blockers)
        high = any(item["severity"] == "high" for item in blockers)
        status = "BLOCKED" if critical else "MANUAL_REVIEW" if high or blockers else "READY"
        return {
            "status": status,
            "blockers": blockers,
            "canary_allowed": status in {"READY", "MANUAL_REVIEW"},
            "production_rollout_allowed": status == "READY",
            "required_checks": [
                "/v1/health/ready",
                "/v1/monitoring/infrastructure/realtime",
                "websocket sequence resume",
                "replay checkpoint validation",
            ],
        }
