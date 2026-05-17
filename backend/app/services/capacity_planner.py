from __future__ import annotations

from typing import Any


class CapacityPlanner:
    """Worker and websocket capacity recommendations for autoscaling policies."""

    def recommend(
        self,
        *,
        active_websockets: int = 0,
        event_throughput: int = 0,
        ai_queue_depth: int = 0,
        gpu_queue_depth: int = 0,
        p95_latency_ms: float = 0.0,
    ) -> dict[str, Any]:
        websocket_instances = max(1, (int(active_websockets) + 799) // 800)
        event_instances = max(1, (int(event_throughput) + 1999) // 2000)
        ai_workers = max(1, (int(ai_queue_depth) + 99) // 100)
        gpu_workers = max(0, (int(gpu_queue_depth) + 31) // 32)
        if p95_latency_ms >= 750:
            websocket_instances += 1
            ai_workers += 1
        return {
            "websocket_instances": min(websocket_instances + event_instances - 1, 12),
            "ai_workers": min(ai_workers, 24),
            "gpu_workers": min(gpu_workers, 16),
            "scale_mode": "SCALE_OUT" if max(ai_queue_depth, gpu_queue_depth, event_throughput) > 0 or p95_latency_ms >= 750 else "HOLD",
            "reason": self._reason(
                active_websockets=active_websockets,
                event_throughput=event_throughput,
                ai_queue_depth=ai_queue_depth,
                gpu_queue_depth=gpu_queue_depth,
                p95_latency_ms=p95_latency_ms,
            ),
        }

    @staticmethod
    def _reason(
        *,
        active_websockets: int,
        event_throughput: int,
        ai_queue_depth: int,
        gpu_queue_depth: int,
        p95_latency_ms: float,
    ) -> str:
        if p95_latency_ms >= 750:
            return "latency pressure"
        if gpu_queue_depth > 0:
            return "gpu inference backlog"
        if ai_queue_depth > 0:
            return "ai worker backlog"
        if event_throughput > 0 or active_websockets > 0:
            return "realtime fanout load"
        return "nominal load"
