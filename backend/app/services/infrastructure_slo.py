from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SLOStatus:
    mode: str
    score: float
    breaches: list[dict[str, Any]]
    actions: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "score": round(self.score * 100, 2),
            "breaches": self.breaches,
            "actions": self.actions,
        }


class InfrastructureSLOEngine:
    """Operational SLO guardrails for realtime infrastructure. No trading side effects."""

    def evaluate(
        self,
        *,
        websocket_latency_ms: float = 0.0,
        sequence_gaps: int = 0,
        stale_feeds: int = 0,
        ai_queue_depth: int = 0,
        gpu_queue_depth: int = 0,
        render_fps: float = 0.0,
        redis_fallback: bool = False,
    ) -> SLOStatus:
        breaches: list[dict[str, Any]] = []
        if websocket_latency_ms >= 750:
            breaches.append({"code": "ws_latency", "severity": "high", "value": websocket_latency_ms})
        if sequence_gaps >= 3:
            breaches.append({"code": "sequence_gaps", "severity": "high", "value": sequence_gaps})
        if stale_feeds >= 2:
            breaches.append({"code": "stale_feeds", "severity": "high", "value": stale_feeds})
        if ai_queue_depth >= 500:
            breaches.append({"code": "ai_queue_backlog", "severity": "medium", "value": ai_queue_depth})
        if gpu_queue_depth >= 250:
            breaches.append({"code": "gpu_queue_backlog", "severity": "medium", "value": gpu_queue_depth})
        if 0 < render_fps < 45:
            breaches.append({"code": "render_fps", "severity": "medium", "value": render_fps})
        if redis_fallback:
            breaches.append({"code": "redis_fallback", "severity": "high", "value": True})

        penalty = sum(0.22 if item["severity"] == "high" else 0.12 for item in breaches)
        score = max(0.0, 1.0 - penalty)
        mode = "NORMAL" if score >= 0.82 else "DEGRADED" if score >= 0.48 else "INCIDENT"
        actions = self._actions(breaches)
        return SLOStatus(mode=mode, score=score, breaches=breaches, actions=actions)

    @staticmethod
    def _actions(breaches: list[dict[str, Any]]) -> list[str]:
        codes = {item["code"] for item in breaches}
        actions = []
        if {"ws_latency", "sequence_gaps", "stale_feeds"} & codes:
            actions.append("force snapshot resume and pause stale chart rendering")
        if {"ai_queue_backlog", "gpu_queue_backlog"} & codes:
            actions.append("shed non-critical analytics jobs and scale workers")
        if "render_fps" in codes:
            actions.append("switch mobile charts to low-power render profile")
        if "redis_fallback" in codes:
            actions.append("disable multi-node fanout until Redis recovers")
        return actions or ["continue normal operations"]
