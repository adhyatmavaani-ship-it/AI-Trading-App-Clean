from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from app.services.realtime_integrity import RealtimeIntegritySequencer


@dataclass(frozen=True)
class ReplayValidationResult:
    valid: bool
    state_hash: str
    mismatch_count: int
    mismatches: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "state_hash": self.state_hash,
            "mismatch_count": self.mismatch_count,
            "mismatches": self.mismatches,
        }


class HistoricalReplayEngine:
    """Deterministic reconstruction and validation for candles, overlays, AI, and orderflow."""

    def build_timeline(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ordered = sorted(
            (dict(event) for event in events),
            key=lambda item: (
                str(item.get("timestamp") or item.get("published_at") or ""),
                int(item.get("sequence_id") or item.get("realtime", {}).get("sequence_id") or 0),
            ),
        )
        return [
            {
                **event,
                "replay_index": index,
                "replay_state_hash": RealtimeIntegritySequencer.state_hash(event),
            }
            for index, event in enumerate(ordered)
        ]

    def validate(self, events: list[dict[str, Any]]) -> ReplayValidationResult:
        timeline = self.build_timeline(events)
        mismatches: list[dict[str, Any]] = []
        for event in timeline:
            expected = event.get("state_hash")
            actual = RealtimeIntegritySequencer.state_hash(event)
            if expected and expected != actual:
                mismatches.append(
                    {
                        "replay_index": event["replay_index"],
                        "event_id": event.get("event_id"),
                        "expected": expected,
                        "actual": actual,
                    }
                )
        timeline_hash = hashlib.sha256(
            json.dumps(
                [event["replay_state_hash"] for event in timeline],
                sort_keys=True,
                default=str,
            ).encode("utf-8")
        ).hexdigest()[:24]
        return ReplayValidationResult(
            valid=not mismatches,
            state_hash=timeline_hash,
            mismatch_count=len(mismatches),
            mismatches=mismatches,
        )
