from __future__ import annotations

from typing import Any


class ConfigDriftDetector:
    """Detects operational config drift from expected safety posture."""

    def detect(
        self,
        *,
        redis_enabled: bool,
        redis_fallback: bool,
        release: dict[str, Any],
        backup: dict[str, Any],
        replay_checkpoint: dict[str, Any],
    ) -> dict[str, Any]:
        drift: list[dict[str, Any]] = []
        if not redis_enabled or redis_fallback:
            drift.append({"code": "redis_not_primary", "severity": "high"})
        if release.get("status") not in {"READY", "MANUAL_REVIEW"}:
            drift.append({"code": "release_gate_not_clear", "severity": "medium"})
        if backup.get("status") != "READY":
            drift.append({"code": "backup_not_ready", "severity": "medium"})
        if replay_checkpoint.get("valid") is not True:
            drift.append({"code": "replay_checkpoint_invalid", "severity": "medium"})
        return {
            "state": "DRIFT" if drift else "IN_POLICY",
            "drift_count": len(drift),
            "items": drift,
            "rollback_safe": not any(item["severity"] == "high" for item in drift),
        }
