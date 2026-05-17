from __future__ import annotations

from typing import Any


class DisasterRecoveryPlanner:
    """Advisory RTO/RPO plan for replay-aware failover."""

    def plan(
        self,
        *,
        backup: dict[str, Any],
        replay_checkpoint: dict[str, Any],
        capacity: dict[str, Any],
        incident: dict[str, Any],
    ) -> dict[str, Any]:
        checkpoint_ok = replay_checkpoint.get("valid") is True
        backup_ready = backup.get("status") == "READY"
        scale_pressure = capacity.get("scale_mode") == "SCALE_OUT"
        severity = str(incident.get("severity", "P3")).upper()
        rto_minutes = 5 if backup_ready and checkpoint_ok and not scale_pressure else 15 if backup_ready else 30
        rpo_seconds = 30 if checkpoint_ok else 300
        return {
            "state": "READY" if backup_ready and checkpoint_ok else "ATTENTION",
            "rto_minutes": rto_minutes,
            "rpo_seconds": rpo_seconds,
            "failover_mode": "HOT_STANDBY" if rto_minutes <= 5 else "WARM_STANDBY",
            "drill_required": severity in {"P0", "P1"} or not checkpoint_ok,
            "steps": [
                "validate latest replay checkpoint state hash",
                "restore Redis Stream replay window before websocket fanout",
                "resume clients via snapshot recovery before sequence resume",
                "verify execution/risk/auth isolation before market open",
            ],
        }
