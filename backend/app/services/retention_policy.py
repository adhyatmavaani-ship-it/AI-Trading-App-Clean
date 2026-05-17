from __future__ import annotations

from typing import Any


class RetentionPolicyPlanner:
    """Advisory retention plan for streams, replay logs, and AI context stores."""

    def plan(
        self,
        *,
        event_count: int = 0,
        replay_count: int = 0,
        ai_context_count: int = 0,
        storage_pressure_pct: float = 0.0,
    ) -> dict[str, Any]:
        pressure = max(float(storage_pressure_pct), self._derived_pressure(event_count, replay_count, ai_context_count))
        if pressure >= 85:
            mode = "AGGRESSIVE"
            hot_days = 3
            replay_days = 14
            max_stream_events = 25_000
        elif pressure >= 60:
            mode = "BALANCED"
            hot_days = 7
            replay_days = 30
            max_stream_events = 50_000
        else:
            mode = "STANDARD"
            hot_days = 14
            replay_days = 90
            max_stream_events = 100_000
        return {
            "mode": mode,
            "storage_pressure_pct": round(pressure, 2),
            "hot_retention_days": hot_days,
            "replay_retention_days": replay_days,
            "ai_context_retention_days": hot_days,
            "max_stream_events": max_stream_events,
            "actions": [
                "trim Redis Streams with MAXLEN approximate policy",
                "archive replay logs before destructive retention",
                "keep trade execution and risk audit records out of realtime retention jobs",
            ],
        }

    @staticmethod
    def _derived_pressure(event_count: int, replay_count: int, ai_context_count: int) -> float:
        weighted = (max(event_count, 0) / 100_000 * 45) + (max(replay_count, 0) / 100_000 * 35) + (max(ai_context_count, 0) / 50_000 * 20)
        return min(weighted, 100.0)
