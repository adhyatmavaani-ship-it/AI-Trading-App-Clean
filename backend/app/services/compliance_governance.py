from __future__ import annotations

from typing import Any


class ComplianceGovernanceEngine:
    """Advisory governance posture for ops dashboards."""

    def evaluate(
        self,
        *,
        drift: dict[str, Any],
        lineage: dict[str, Any],
        audit: dict[str, Any],
        backup: dict[str, Any],
    ) -> dict[str, Any]:
        gaps: list[str] = []
        if drift.get("state") != "IN_POLICY":
            gaps.append("configuration drift present")
        if lineage.get("contains_secrets") is not False:
            gaps.append("lineage manifest secret status unknown")
        if audit.get("manifest_version") == "unknown":
            gaps.append("audit manifest unavailable")
        if backup.get("status") != "READY":
            gaps.append("backup not ready")
        return {
            "state": "COMPLIANT" if not gaps else "REVIEW",
            "gaps": gaps,
            "controls": [
                "risk and execution audit records are excluded from realtime retention compaction",
                "release readiness is advisory and does not mutate deployment state",
                "runbook steps require an operator",
                "lineage manifests exclude secrets and raw user chat",
            ],
        }
