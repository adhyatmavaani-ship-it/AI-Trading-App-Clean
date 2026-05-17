from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class IncidentResponseEngine:
    """Builds an incident snapshot and runbook hints without mutating runtime state."""

    def snapshot(
        self,
        *,
        slo: dict[str, Any],
        high_availability: dict[str, Any],
        replay_checkpoint: dict[str, Any],
        redis_fallback: bool,
    ) -> dict[str, Any]:
        slo_mode = str(slo.get("mode", "UNKNOWN")).upper()
        ha_mode = str(high_availability.get("mode", "UNKNOWN")).upper()
        replay_ok = replay_checkpoint.get("valid") is True
        severity = "P0" if slo_mode == "INCIDENT" or redis_fallback else "P1" if slo_mode == "DEGRADED" or ha_mode == "DEGRADED" else "P3"
        if not replay_ok and severity == "P3":
            severity = "P2"
        runbook = self._runbook(
            severity=severity,
            slo_actions=list(slo.get("actions") or []),
            ha_actions=list(high_availability.get("actions") or []),
            replay_ok=replay_ok,
        )
        return {
            "incident_id": self._incident_id(severity=severity, slo=slo),
            "severity": severity,
            "status": "OPEN" if severity in {"P0", "P1", "P2"} else "WATCH",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "summary": self._summary(severity=severity, slo_mode=slo_mode, ha_mode=ha_mode, replay_ok=replay_ok),
            "runbook": runbook,
            "rollback_safe": severity != "P0" and replay_ok,
            "requires_human": severity in {"P0", "P1"},
        }

    @staticmethod
    def _incident_id(*, severity: str, slo: dict[str, Any]) -> str:
        breach_codes = "-".join(str(item.get("code", "unknown")) for item in slo.get("breaches", [])[:3])
        return f"{severity}-{breach_codes or 'watch'}"

    @staticmethod
    def _summary(*, severity: str, slo_mode: str, ha_mode: str, replay_ok: bool) -> str:
        replay = "checkpoint ok" if replay_ok else "checkpoint missing"
        return f"{severity} realtime health: SLO {slo_mode}, HA {ha_mode}, {replay}."

    @staticmethod
    def _runbook(*, severity: str, slo_actions: list[str], ha_actions: list[str], replay_ok: bool) -> list[str]:
        steps = []
        if not replay_ok:
            steps.append("create fresh chart snapshot checkpoint before replay-dependent debugging")
        steps.extend(slo_actions)
        steps.extend(ha_actions)
        if severity in {"P0", "P1"}:
            steps.append("freeze non-critical AI analytics and preserve execution/risk isolation")
        steps.append("verify /v1/health/ready and websocket sequence recovery before closing")
        return list(dict.fromkeys(step for step in steps if step))
