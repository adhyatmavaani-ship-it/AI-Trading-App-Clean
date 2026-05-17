from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.redis_cache import RedisCache
from app.services.realtime_integrity import RealtimeIntegritySequencer


class ReplayCheckpointStore:
    """Stores lightweight replay checkpoints for fast recovery and audit."""

    def __init__(self, cache: RedisCache, *, prefix: str = "replay:checkpoint") -> None:
        self.cache = cache
        self.prefix = prefix

    def save(
        self,
        *,
        stream: str,
        sequence_id: int,
        state: dict[str, Any],
        ttl: int = 60 * 60 * 24,
    ) -> dict[str, Any]:
        state_hash = RealtimeIntegritySequencer.state_hash(state)
        checkpoint = {
            "stream": stream,
            "sequence_id": int(sequence_id),
            "state_hash": state_hash,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "state": state,
        }
        self.cache.set_json(self._key(stream), checkpoint, ttl=ttl)
        return checkpoint

    def load(self, *, stream: str) -> dict[str, Any] | None:
        return self.cache.get_json(self._key(stream))

    def validate(self, *, stream: str) -> dict[str, Any]:
        checkpoint = self.load(stream=stream)
        if not checkpoint:
            return {"valid": False, "reason": "missing_checkpoint"}
        actual = RealtimeIntegritySequencer.state_hash(dict(checkpoint.get("state") or {}))
        expected = str(checkpoint.get("state_hash") or "")
        return {
            "valid": expected == actual,
            "expected": expected,
            "actual": actual,
            "sequence_id": int(checkpoint.get("sequence_id") or 0),
        }

    def _key(self, stream: str) -> str:
        return f"{self.prefix}:{stream}"
