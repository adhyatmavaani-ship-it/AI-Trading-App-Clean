from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any

import pandas as pd

from app.core.config import Settings
from app.services.redis_cache import RedisCache

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MarketFeedHealth:
    symbol: str
    interval: str
    healthy: bool
    status: str
    reasons: list[str]
    last_timestamp_ms: int | None
    age_seconds: float | None
    volume_ratio: float | None

    def to_payload(self) -> dict[str, Any]:
        checked_at = datetime.now(timezone.utc)
        return {
            "symbol": self.symbol,
            "interval": self.interval,
            "healthy": self.healthy,
            "status": self.status,
            "reasons": self.reasons,
            "health_reason": "healthy" if self.healthy else ", ".join(self.reasons),
            "last_timestamp_ms": self.last_timestamp_ms,
            "age_seconds": self.age_seconds,
            "producer_last_seen_ts": checked_at.isoformat(),
            "producer_age_ms": 0.0,
            "volume_ratio": self.volume_ratio,
            "checked_at": checked_at.isoformat(),
        }


@dataclass
class MarketFeedWatchdog:
    settings: Settings
    cache: RedisCache

    def evaluate_frame(self, symbol: str, interval: str, frame: pd.DataFrame) -> MarketFeedHealth:
        normalized_symbol = str(symbol or "").upper().strip()
        normalized_interval = str(interval or "").strip() or "unknown"
        reasons: list[str] = []
        last_timestamp_ms = self._last_timestamp_ms(frame)
        age_seconds: float | None = None
        volume_ratio = self._latest_volume_ratio(frame)

        if frame.empty:
            reasons.append("market unavailable")
        if last_timestamp_ms is None:
            reasons.append("missing candle timestamp")
        else:
            age_seconds = max(
                0.0,
                datetime.now(timezone.utc).timestamp() - (last_timestamp_ms / 1000.0),
            )
            max_age = self._max_age_seconds(normalized_interval)
            if age_seconds > max_age:
                reasons.append("market feed stale")
        if self._has_frozen_timestamps(frame):
            reasons.append("frozen candle timestamps")
        if (
            volume_ratio is not None
            and volume_ratio > float(self.settings.market_feed_max_volume_spike_ratio)
        ):
            reasons.append("impossible volume spike")

        healthy = not reasons
        health = MarketFeedHealth(
            symbol=normalized_symbol,
            interval=normalized_interval,
            healthy=healthy,
            status="healthy" if healthy else "unhealthy",
            reasons=reasons,
            last_timestamp_ms=last_timestamp_ms,
            age_seconds=round(age_seconds, 4) if age_seconds is not None else None,
            volume_ratio=round(volume_ratio, 4) if volume_ratio is not None else None,
        )
        self.record_health(health)
        return health

    def record_health(self, health: MarketFeedHealth) -> None:
        ttl = int(self.settings.monitor_state_ttl_seconds)
        payload = health.to_payload()
        self.cache.set_json(
            f"market:feed:health:{health.symbol}:{health.interval}",
            payload,
            ttl=ttl,
        )
        self.cache.set_json("market:feed:health", payload, ttl=ttl)
        if health.healthy and health.last_timestamp_ms is not None:
            self.cache.set(
                "market:feed:last_seen_ts",
                str(health.last_timestamp_ms / 1000.0),
                ttl=ttl,
            )
            return
        self.cache.increment("monitor:websocket_stale_feed_count", ttl=ttl)
        logger.warning(
            "market_feed_watchdog_unhealthy",
            extra={
                "event": "market_feed_watchdog_unhealthy",
                "context": {
                    "symbol": health.symbol,
                    "interval": health.interval,
                    "status": health.status,
                    "reasons": health.reasons,
                    "age_seconds": health.age_seconds,
                    "volume_ratio": health.volume_ratio,
                },
            },
        )

    def _max_age_seconds(self, interval: str) -> float:
        interval_seconds = {
            "1m": 60,
            "3m": 180,
            "5m": 300,
            "15m": 900,
            "30m": 1800,
            "1h": 3600,
            "4h": 14_400,
            "1d": 86_400,
        }.get(interval, 300)
        return max(
            float(self.settings.market_feed_min_stale_seconds),
            interval_seconds * float(self.settings.market_feed_stale_multiplier),
        )

    @staticmethod
    def _last_timestamp_ms(frame: pd.DataFrame) -> int | None:
        if frame.empty:
            return None
        for column in ("close_time", "timestamp", "open_time"):
            if column not in frame.columns:
                continue
            try:
                value = float(frame[column].iloc[-1])
            except Exception:
                continue
            if value <= 0:
                continue
            return int(value * 1000) if value < 10_000_000_000 else int(value)
        return None

    @staticmethod
    def _has_frozen_timestamps(frame: pd.DataFrame) -> bool:
        if frame.empty:
            return False
        for column in ("close_time", "timestamp", "open_time"):
            if column not in frame.columns:
                continue
            series = pd.to_numeric(frame[column], errors="coerce").dropna().tail(4)
            if len(series) < 3:
                return False
            deltas = series.diff().dropna()
            return bool((deltas <= 0).any())
        return False

    @staticmethod
    def _latest_volume_ratio(frame: pd.DataFrame) -> float | None:
        if frame.empty or "volume" not in frame.columns:
            return None
        volumes = pd.to_numeric(frame["volume"], errors="coerce").dropna()
        if len(volumes) < 3:
            return None
        latest = float(volumes.iloc[-1])
        baseline = float(volumes.iloc[:-1].tail(min(20, len(volumes) - 1)).mean() or 0.0)
        if baseline <= 0:
            return None
        return latest / baseline
