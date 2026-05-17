from __future__ import annotations

from typing import Any


class HighAvailabilityPlanner:
    """Health-aware degradation plan for websocket and worker infrastructure."""

    def plan(self, *, redis_fallback: bool, queue_depth: int, websocket_gaps: int, stale_feeds: int) -> dict[str, Any]:
        actions = []
        if redis_fallback:
            actions.append("pin websocket fanout to single instance until Redis recovers")
        if queue_depth >= 500:
            actions.append("scale AI/GPU workers before accepting new heavy analytics jobs")
        if websocket_gaps >= 3 or stale_feeds >= 2:
            actions.append("force snapshot recovery and pause stale chart rendering")
        mode = "DEGRADED" if actions else "NORMAL"
        return {
            "mode": mode,
            "actions": actions,
            "rolling_deploy_safe": not redis_fallback,
            "websocket_reconnect_strategy": "snapshot_resume" if mode == "DEGRADED" else "sequence_resume",
        }
