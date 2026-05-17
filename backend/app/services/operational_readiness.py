from __future__ import annotations

from typing import Any


class OperationalReadinessEngine:
    """Single advisory readiness verdict from the monitoring stack."""

    def evaluate(
        self,
        *,
        slo: dict[str, Any],
        release: dict[str, Any],
        compliance: dict[str, Any],
        disaster_recovery: dict[str, Any],
        config_drift: dict[str, Any],
        backup: dict[str, Any],
    ) -> dict[str, Any]:
        penalties = 0.0
        actions: list[str] = []
        if slo.get("mode") == "INCIDENT":
            penalties += 0.35
            actions.append("resolve realtime SLO incident before rollout")
        elif slo.get("mode") == "DEGRADED":
            penalties += 0.18
            actions.append("stabilize realtime SLO before increasing load")
        if release.get("status") == "BLOCKED":
            penalties += 0.28
            actions.append("clear release blockers")
        elif release.get("status") == "MANUAL_REVIEW":
            penalties += 0.12
            actions.append("complete manual release review")
        if compliance.get("state") != "COMPLIANT":
            penalties += 0.16
            actions.append("review compliance gaps")
        if disaster_recovery.get("state") != "READY":
            penalties += 0.12
            actions.append("complete DR checkpoint and backup validation")
        if config_drift.get("state") == "DRIFT":
            penalties += 0.12
            actions.append("resolve config drift")
        if backup.get("status") != "READY":
            penalties += 0.10
            actions.append("verify backup readiness")

        score = max(0.0, 1.0 - min(penalties, 1.0))
        if score >= 0.86:
            status = "READY"
        elif score >= 0.62:
            status = "WATCH"
        elif score >= 0.40:
            status = "DEGRADED"
        else:
            status = "BLOCKED"
        return {
            "status": status,
            "score": round(score * 100, 2),
            "actions": actions or ["continue normal operations"],
            "safe_for_release": status == "READY" and release.get("production_rollout_allowed") is True,
            "safe_for_scale_out": status in {"READY", "WATCH"},
            "advisory_only": True,
        }
