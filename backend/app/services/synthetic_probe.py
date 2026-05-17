from __future__ import annotations

from typing import Any


class SyntheticProbePlanner:
    """Read-only synthetic probe plan for API, websocket, and replay paths."""

    def plan(self, *, release: dict[str, Any], slo: dict[str, Any]) -> dict[str, Any]:
        release_ready = release.get("status") == "READY"
        slo_normal = slo.get("mode") == "NORMAL"
        interval_seconds = 30 if release_ready and slo_normal else 10
        return {
            "mode": "STANDARD" if release_ready and slo_normal else "HEIGHTENED",
            "interval_seconds": interval_seconds,
            "probes": [
                {"name": "health_ready", "target": "/v1/health/ready", "timeout_ms": 1200},
                {"name": "infrastructure_snapshot", "target": "/v1/monitoring/infrastructure/realtime", "timeout_ms": 1500},
                {"name": "websocket_probe", "target": "signals websocket ping/pong", "timeout_ms": 2500},
                {"name": "replay_resume", "target": "chart snapshot replay validation", "timeout_ms": 3000},
            ],
        }
