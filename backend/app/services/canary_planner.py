from __future__ import annotations

from typing import Any


class CanaryPlanner:
    """Creates canary rollout guidance without changing deployment state."""

    def plan(self, *, release: dict[str, Any], capacity: dict[str, Any]) -> dict[str, Any]:
        if release.get("canary_allowed") is not True:
            return {
                "mode": "DISABLED",
                "traffic_steps": [],
                "abort_conditions": ["release gate blocked"],
            }
        pressure = capacity.get("scale_mode") == "SCALE_OUT"
        steps = [1, 5, 10] if pressure else [1, 5, 15, 30]
        return {
            "mode": "CONSERVATIVE" if pressure else "STANDARD",
            "traffic_steps": steps,
            "hold_minutes": 10 if pressure else 6,
            "abort_conditions": [
                "SLO mode changes to INCIDENT",
                "websocket sequence gaps increase",
                "replay checkpoint validation fails",
                "p95 websocket latency exceeds 750ms",
            ],
        }
