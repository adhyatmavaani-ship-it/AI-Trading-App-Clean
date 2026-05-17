from __future__ import annotations

from typing import Any


class RollbackPlanner:
    """Manual rollback plan. It never executes git, deploy, or infra commands."""

    def plan(self, *, release: dict[str, Any], incident: dict[str, Any]) -> dict[str, Any]:
        severity = str(incident.get("severity", "P3")).upper()
        blocked = release.get("status") == "BLOCKED"
        return {
            "recommended": blocked or severity in {"P0", "P1"},
            "strategy": "immediate_previous_version" if blocked or severity == "P0" else "hold_and_monitor",
            "steps": [
                "freeze canary traffic",
                "preserve replay checkpoints and websocket sequence ranges",
                "rollback application image only after /health/ready confirms target",
                "do not alter execution/risk/auth/paper-live configuration during rollback",
            ],
            "validation": [
                "/v1/health/ready returns ready",
                "infrastructure SLO returns NORMAL or DEGRADED without critical blockers",
                "websocket resumes via snapshot or sequence recovery",
            ],
        }
