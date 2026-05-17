from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class AuditExportPlanner:
    """Builds export metadata for operator handoff without writing files."""

    def build_manifest(
        self,
        *,
        incident: dict[str, Any],
        release: dict[str, Any],
        runbook: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "manifest_version": "ops-audit-v1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "sections": [
                "incident",
                "release_readiness",
                "runbook",
                "slo",
                "capacity",
                "retention",
                "replay_checkpoint",
            ],
            "incident_severity": incident.get("severity", "UNKNOWN"),
            "release_status": release.get("status", "UNKNOWN"),
            "runbook_step_count": len(runbook.get("steps") or []),
            "privacy": "operational metadata only; no secrets or raw user chat",
        }
