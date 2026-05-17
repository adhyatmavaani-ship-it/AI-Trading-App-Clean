from __future__ import annotations

from typing import Any


class RunbookOrchestrator:
    """Produces safe runbook steps. It does not execute shell or mutate infra."""

    def build(
        self,
        *,
        incident: dict[str, Any],
        capacity: dict[str, Any],
        retention: dict[str, Any],
    ) -> dict[str, Any]:
        steps = list(incident.get("runbook") or [])
        if capacity.get("scale_mode") == "SCALE_OUT":
            steps.append(
                f"scale websocket={capacity.get('websocket_instances')} ai={capacity.get('ai_workers')} gpu={capacity.get('gpu_workers')}"
            )
        if retention.get("mode") in {"BALANCED", "AGGRESSIVE"}:
            steps.append("schedule replay/archive retention task outside market open")
        steps.append("capture post-incident timeline with state hashes and websocket sequence ranges")
        return {
            "safe_to_auto_apply": False,
            "steps": list(dict.fromkeys(step for step in steps if step)),
            "operator_required": True,
            "rollback_note": "Rollback by disabling advisory Phase 7 dashboards; execution and risk pipelines are not coupled to these actions.",
        }
