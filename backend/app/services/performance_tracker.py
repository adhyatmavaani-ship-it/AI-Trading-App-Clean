from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.services.redis_cache import RedisCache

if TYPE_CHECKING:
    from app.services.firestore_repo import FirestoreRepository


@dataclass
class PerformanceTracker:
    cache: RedisCache
    firestore: FirestoreRepository

    def source_metrics(self) -> dict:
        return self.cache.get_json("alpha:source_metrics") or {}

    def record_signal_outcome(
        self,
        signal_type: str,
        signal_id: str,
        profit: float,
        correlation: float,
    ) -> dict:
        key = f"signal_perf:{signal_type}"
        state = self.cache.get_json(key) or {
            "wins": 0,
            "trades": 0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "avg_correlation": 0.0,
        }
        state["trades"] += 1
        state["wins"] += int(profit > 0)
        state["gross_profit"] += max(0.0, profit)
        state["gross_loss"] += abs(min(0.0, profit))
        prev_n = max(state["trades"] - 1, 0)
        state["avg_correlation"] = (
            (state["avg_correlation"] * prev_n + correlation) / max(state["trades"], 1)
        )
        snapshot = {
            "signal_type": signal_type,
            "signal_id": signal_id,
            "win_rate": state["wins"] / max(state["trades"], 1),
            "profit_factor": state["gross_profit"] / max(state["gross_loss"], 1e-8),
            "avg_correlation": state["avg_correlation"],
            "trades": state["trades"],
        }
        self.cache.set_json(key, state, ttl=86_400)

        source_metrics = self.cache.get_json("alpha:source_metrics") or {}
        source_metrics[signal_type] = {
            "win_rate": snapshot["win_rate"],
            "profit_factor": snapshot["profit_factor"],
            "drift_penalty": max(0.0, snapshot["avg_correlation"] - 0.7),
        }
        self.cache.set_json("alpha:source_metrics", source_metrics, ttl=86_400)
        self.firestore.save_performance_snapshot(signal_type, snapshot)
        return snapshot
