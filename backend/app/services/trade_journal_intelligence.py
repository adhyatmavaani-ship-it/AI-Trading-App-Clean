from __future__ import annotations

from typing import Any

from app.services.redis_cache import RedisCache


class TradeJournalIntelligence:
    """Privacy-safe behavioral journal. Stores structured signals, not raw chat."""

    def __init__(self, cache: RedisCache, *, prefix: str = "journal") -> None:
        self.cache = cache
        self.prefix = prefix

    def record(self, *, user_id: str, event: dict[str, Any], ttl: int = 60 * 60 * 24 * 30) -> dict[str, Any]:
        key = self._key(user_id)
        current = self.cache.get_json(key) or {"events": []}
        events = list(current.get("events") or [])
        sanitized = {
            "type": str(event.get("type", "decision")),
            "symbol": str(event.get("symbol", ""))[:24],
            "setup_quality": float(event.get("setup_quality", 0.0) or 0.0),
            "risk_state": str(event.get("risk_state", "UNKNOWN"))[:40],
            "followed_plan": bool(event.get("followed_plan", True)),
        }
        events.append(sanitized)
        events = events[-250:]
        summary = self._summary(events)
        self.cache.set_json(key, {"events": events, "summary": summary}, ttl=ttl)
        return summary

    def load_summary(self, *, user_id: str) -> dict[str, Any]:
        current = self.cache.get_json(self._key(user_id)) or {}
        return dict(current.get("summary") or self._summary([]))

    @staticmethod
    def _summary(events: list[dict[str, Any]]) -> dict[str, Any]:
        if not events:
            return {"behavioral_risk_score": 0.0, "discipline_score": 100.0, "bias_flags": [], "event_count": 0}
        failed_plan = sum(1 for event in events if not event.get("followed_plan", True))
        low_quality = sum(1 for event in events if float(event.get("setup_quality", 0.0) or 0.0) < 50)
        behavioral_risk = min(((failed_plan * 0.65) + (low_quality * 0.35)) / max(len(events), 1), 1.0)
        flags = []
        if failed_plan >= 3:
            flags.append("execution_discipline_drift")
        if low_quality >= 4:
            flags.append("low_quality_setup_repetition")
        return {
            "behavioral_risk_score": round(behavioral_risk * 100, 2),
            "discipline_score": round((1.0 - failed_plan / max(len(events), 1)) * 100, 2),
            "bias_flags": flags,
            "event_count": len(events),
        }

    def _key(self, user_id: str) -> str:
        return f"{self.prefix}:{user_id}:behavior"
