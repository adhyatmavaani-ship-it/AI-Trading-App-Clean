from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.redis_cache import RedisCache


class AIContextMemory:
    def __init__(self, cache: RedisCache, *, ttl_seconds: int = 86_400) -> None:
        self.cache = cache
        self.ttl_seconds = max(int(ttl_seconds), 60)

    def remember(self, *, symbol: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        key = self._key(symbol)
        current = self.cache.get_json(key) or {"events": []}
        events = list(current.get("events", []))
        item = {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        events.append(item)
        events = events[-100:]
        summary = self._summary(events)
        state = {"symbol": symbol.upper(), "events": events, "summary": summary}
        self.cache.set_json(key, state, ttl=self.ttl_seconds)
        return summary

    def load_summary(self, *, symbol: str) -> dict[str, Any]:
        state = self.cache.get_json(self._key(symbol)) or {}
        return dict(state.get("summary") or {})

    def _summary(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for event in events:
            event_type = str(event.get("event_type") or "unknown")
            counts[event_type] = counts.get(event_type, 0) + 1
        return {
            "event_counts": counts,
            "recent_event_count": len(events),
            "confidence_adjustment": round(
                -0.05 * counts.get("failed_breakout", 0)
                -0.03 * counts.get("repeated_liquidity_sweep", 0)
                +0.02 * counts.get("validated_continuation", 0),
                4,
            ),
        }

    @staticmethod
    def _key(symbol: str) -> str:
        return f"ai:context:{str(symbol or 'UNKNOWN').upper()}"
