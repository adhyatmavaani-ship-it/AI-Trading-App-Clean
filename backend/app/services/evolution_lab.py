from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.core.config import Settings

if TYPE_CHECKING:
    from app.services.firestore_repo import FirestoreRepository
    from app.services.redis_cache import RedisCache


@dataclass
class EvolutionLab:
    settings: Settings
    cache: RedisCache
    firestore: FirestoreRepository | None = None

    def breed_child_bots(self, parent_config: dict, count: int = 10) -> list[dict]:
        children = []
        for index in range(count):
            child = {
                "bot_id": f"child-bot-{index + 1}",
                "parent": parent_config.get("bot_id", "master"),
                "stop_loss_pct": round(max(0.005, float(parent_config.get("stop_loss_pct", 0.02)) + random.uniform(-0.005, 0.003)), 6),
                "rsi_length": max(7, int(parent_config.get("rsi_length", 14) + random.choice([-3, -1, 1, 2]))),
                "volatility_filter": round(max(0.0, float(parent_config.get("volatility_filter", 0.02)) + random.uniform(-0.005, 0.005)), 6),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            children.append(child)
        self.cache.set_json("evolution:children", {"children": children}, ttl=self.settings.monitor_state_ttl_seconds)
        return children

    def evaluate_children(self, children: list[dict], simulation_results: list[dict]) -> dict:
        leaderboard = []
        for child, result in zip(children, simulation_results):
            score = (
                float(result.get("profit_factor", 0.0)) * 0.5
                + float(result.get("win_rate", 0.0)) * 0.3
                - float(result.get("max_drawdown", 0.0)) * 0.2
            )
            leaderboard.append({**child, "score": round(score, 6), "simulation": result})
        leaderboard.sort(key=lambda item: item["score"], reverse=True)
        best = leaderboard[0] if leaderboard else None
        if best is not None:
            candidate = {
                "candidate": best,
                "approval_required": True,
                "reason": "Automatic promotion to production is disabled; review before promotion.",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            self.cache.set_json("evolution:promotion_candidate", candidate, ttl=self.settings.monitor_state_ttl_seconds)
            if self.firestore is not None:
                self.firestore.save_performance_snapshot("evolution:promotion_candidate", candidate)
        return {
            "leaderboard": leaderboard,
            "promotion_candidate": self.cache.get_json("evolution:promotion_candidate"),
        }

