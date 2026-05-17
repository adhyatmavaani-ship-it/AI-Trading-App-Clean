from __future__ import annotations

from typing import Any


class OrderbookDeltaValidator:
    """Validates depth delta continuity before applying it to DOM state."""

    def validate(
        self,
        *,
        current_sequence: int,
        incoming_sequence: int,
        bid_updates: list[tuple[float, float]],
        ask_updates: list[tuple[float, float]],
    ) -> dict[str, Any]:
        current = int(current_sequence)
        incoming = int(incoming_sequence)
        if incoming <= current:
            return {
                "action": "DROP_DUPLICATE",
                "valid": False,
                "missing_range": [],
                "reason": "stale_or_duplicate_depth_delta",
            }
        missing = list(range(current + 1, incoming)) if incoming > current + 1 else []
        invalid_price = any(float(price) <= 0 for price, _ in bid_updates + ask_updates)
        invalid_size = any(float(size) < 0 for _, size in bid_updates + ask_updates)
        if invalid_price or invalid_size:
            return {
                "action": "REQUEST_SNAPSHOT",
                "valid": False,
                "missing_range": missing,
                "reason": "invalid_depth_level",
            }
        if missing:
            return {
                "action": "REQUEST_REPLAY",
                "valid": False,
                "missing_range": missing[:100],
                "reason": "sequence_gap",
            }
        return {
            "action": "APPLY_DELTA",
            "valid": True,
            "missing_range": [],
            "reason": "ok",
        }
