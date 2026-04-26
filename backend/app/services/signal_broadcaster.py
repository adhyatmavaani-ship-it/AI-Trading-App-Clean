from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging

from app.core.config import Settings
from app.services.execution_queue_manager import ExecutionQueueManager
from app.services.redis_cache import RedisCache


logger = logging.getLogger(__name__)


@dataclass
class SignalBroadcaster:
    settings: Settings
    cache: RedisCache
    queue_manager: ExecutionQueueManager

    def publish_signal(self, signal: dict) -> dict:
        version = self.cache.increment("signals:version", ttl=self.settings.signal_version_ttl_seconds)
        envelope = {
            **signal,
            "signal_version": version,
            "published_at": datetime.now(timezone.utc).isoformat(),
        }
        self.cache.set_json(
            f"signal:latest:{signal['symbol']}",
            envelope,
            ttl=self.settings.signal_version_ttl_seconds,
        )
        self._safe_publish(
            channel=self.settings.signal_broadcast_channel,
            payload=envelope,
            event="signal_broadcast_publish_failed",
        )
        subscriptions = self.list_subscriptions()
        eligible = self.filter_subscriptions(envelope, subscriptions)
        distribution = self.queue_manager.enqueue_signal(envelope, eligible)
        fanout = {**distribution, "eligible_subscribers": len(eligible), "signal_version": version}
        self._safe_publish(
            channel=self.settings.signal_execution_channel,
            payload={"symbol": signal["symbol"], "signal_version": version, **distribution},
            event="signal_execution_publish_failed",
        )
        return {**envelope, "distribution": fanout}

    def register_subscription(self, user_id: str, tier: str, balance: float, risk_profile: str) -> None:
        self.cache.set_json(
            f"subscription:{user_id}",
            {
                "user_id": user_id,
                "tier": tier,
                "balance": balance,
                "risk_profile": risk_profile,
            },
            ttl=self.settings.signal_version_ttl_seconds,
        )

    def list_subscriptions(self) -> list[dict]:
        subscriptions: list[dict] = []
        for key in self.cache.keys("subscription:*"):
            payload = self.cache.get_json(key)
            if payload:
                subscriptions.append(payload)
        return subscriptions

    def filter_subscriptions(self, signal: dict, subscriptions: list[dict]) -> list[dict]:
        allowed_profiles = {profile.lower() for profile in signal.get("allowed_risk_profiles", ["conservative", "moderate", "aggressive"])}
        required_tier = str(signal.get("required_tier", "free")).lower()
        min_balance = float(signal.get("min_balance", 0.0))
        eligible: list[dict] = []
        for subscription in subscriptions:
            if not self._tier_allows(str(subscription.get("tier", "free")).lower(), required_tier):
                continue
            if float(subscription.get("balance", 0.0)) < min_balance:
                continue
            if str(subscription.get("risk_profile", "moderate")).lower() not in allowed_profiles:
                continue
            eligible.append(subscription)
        return eligible

    def _tier_allows(self, actual: str, required: str) -> bool:
        order = {"free": 0, "pro": 1, "vip": 2, "institutional": 3}
        return order.get(actual, 0) >= order.get(required, 0)

    def _safe_publish(self, *, channel: str, payload: dict, event: str) -> None:
        try:
            self.cache.publish(channel, json.dumps(payload))
        except Exception as exc:
            logger.warning(
                event,
                extra={
                    "event": event,
                    "context": {
                        "channel": channel,
                        "error": str(exc)[:200],
                    },
                },
            )

