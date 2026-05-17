from __future__ import annotations

from typing import Any


class BackupReadinessPlanner:
    """Advisory backup coverage for replay and operational state."""

    def plan(self, *, replay_checkpoint: dict[str, Any], retention: dict[str, Any]) -> dict[str, Any]:
        checkpoint_ok = replay_checkpoint.get("valid") is True
        retention_mode = str(retention.get("mode", "UNKNOWN")).upper()
        status = "READY" if checkpoint_ok and retention_mode != "UNKNOWN" else "ATTENTION"
        return {
            "status": status,
            "checkpoint_ready": checkpoint_ok,
            "retention_mode": retention_mode,
            "targets": [
                "Redis Stream replay logs",
                "AI context summaries",
                "chart snapshot checkpoints",
                "monitoring incident snapshots",
            ],
            "exclusions": [
                "do not compact trade execution audit records",
                "do not compact risk decision audit records",
            ],
        }
