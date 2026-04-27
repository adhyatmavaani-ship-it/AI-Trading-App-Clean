from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json

from app.core.config import Settings
from app.services.redis_cache import RedisCache


@dataclass
class UserExperienceEngine:
    settings: Settings
    cache: RedisCache

    def publish_activity(
        self,
        *,
        status: str,
        message: str,
        bot_state: str,
        symbol: str | None = None,
        next_scan: str | None = None,
        confidence: float | None = None,
        action: str | None = None,
        intent: str | None = None,
        confidence_building: bool | None = None,
        readiness: float | None = None,
        reason: str | None = None,
        extra: dict | None = None,
    ) -> dict:
        normalized_symbol = str(symbol or "").upper() or None
        payload = {
            "type": "activity",
            "status": status,
            "bot_state": bot_state,
            "mode": self.settings.user_experience_mode.upper(),
            "message": message,
            "symbol": normalized_symbol,
            "next_scan": str(next_scan or "").upper() or None,
            "confidence": round(float(confidence), 8) if confidence is not None else None,
            "action": action,
            "intent": intent,
            "confidence_building": bool(confidence_building) if confidence_building is not None else None,
            "readiness": round(float(readiness), 2) if readiness is not None else None,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **(extra or {}),
        }
        self.cache.set_json(
            "activity:latest",
            payload,
            ttl=self.settings.signal_version_ttl_seconds,
        )
        self._append_history(payload)
        self._update_readiness_board(normalized_symbol, payload)
        self.cache.publish(self.settings.live_activity_channel, json.dumps(payload))
        return payload

    def latest(self) -> dict:
        return self.cache.get_json("activity:latest") or {}

    def history(self, limit: int = 25) -> list[dict]:
        bucket = self.cache.get_json("activity:history") or {"items": []}
        items = list(bucket.get("items", []))
        return items[-max(1, limit) :]

    def readiness(self, limit: int = 8) -> list[dict]:
        bucket = self.cache.get_json("activity:readiness") or {"items": []}
        items = list(bucket.get("items", []))
        items.sort(
            key=lambda item: (
                -float(item.get("readiness", 0.0) or 0.0),
                str(item.get("updated_at", "")),
            ),
        )
        return items[: max(1, limit)]

    def _append_history(self, payload: dict) -> None:
        bucket = self.cache.get_json("activity:history") or {"items": []}
        items = list(bucket.get("items", []))
        items.append(payload)
        keep = max(int(self.settings.activity_history_limit), 1)
        self.cache.set_json(
            "activity:history",
            {"items": items[-keep:]},
            ttl=self.settings.signal_version_ttl_seconds,
        )

    def _update_readiness_board(self, symbol: str | None, payload: dict) -> None:
        if not symbol:
            return
        bucket = self.cache.get_json("activity:readiness") or {"items": []}
        items = list(bucket.get("items", []))
        board = [item for item in items if str(item.get("symbol", "")).upper() != symbol]
        board.append(
            {
                "symbol": symbol,
                "readiness": round(float(payload.get("readiness", 0.0) or 0.0), 2),
                "status": str(payload.get("status", "scanning")),
                "intent": payload.get("intent"),
                "confidence_building": payload.get("confidence_building"),
                "confidence": payload.get("confidence"),
                "confidence_meter": payload.get("confidence_meter"),
                "strict_trade_score": payload.get("strict_trade_score"),
                "reason": payload.get("reason"),
                "message": payload.get("message"),
                "regime": payload.get("regime"),
                "bot_state": payload.get("bot_state"),
                "updated_at": payload.get("timestamp"),
            }
        )
        keep = max(int(self.settings.activity_history_limit), 1)
        self.cache.set_json(
            "activity:readiness",
            {"items": board[-keep:]},
            ttl=self.settings.signal_version_ttl_seconds,
        )
