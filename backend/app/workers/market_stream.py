from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

import websockets

from app.core.config import get_settings
from app.services.redis_cache import RedisCache

logger = logging.getLogger(__name__)


async def stream_trades() -> None:
    """Consumes Binance streams and stores the latest ticks and book state in Redis."""
    settings = get_settings()
    cache = RedisCache(settings.redis_url)
    streams = "/".join(
        stream
        for symbol in settings.websocket_symbols
        for stream in (
            f"{symbol.lower()}@trade",
            f"{symbol.lower()}@bookTicker",
            f"{symbol.lower()}@miniTicker",
        )
    )
    url = f"wss://stream.binance.com:9443/stream?streams={streams}"
    async with websockets.connect(url) as socket:
        _record_websocket_health(cache, connected=True)
        async for message in socket:
            payload = json.loads(message)
            stream = payload["stream"]
            data = payload["data"]
            _record_websocket_health(cache, connected=True)
            cache.set_json(f"stream:{stream}", data, ttl=30)
            if stream.endswith("@bookTicker"):
                symbol = str(data.get("s", "")).upper()
                cache.set_json(
                    f"stream:book:{symbol}",
                    {
                        "symbol": symbol,
                        "best_bid": float(data.get("b", 0.0)),
                        "best_bid_qty": float(data.get("B", 0.0)),
                        "best_ask": float(data.get("a", 0.0)),
                        "best_ask_qty": float(data.get("A", 0.0)),
                    },
                    ttl=30,
                )


def _record_websocket_health(cache: RedisCache, *, connected: bool) -> None:
    now = datetime.now(timezone.utc).isoformat()
    ttl = int(get_settings().monitor_state_ttl_seconds)
    cache.set("monitor:websocket_connected", "1" if connected else "0", ttl=ttl)
    cache.set("monitor:websocket_connected:last_seen_ts", now, ttl=ttl)


def run() -> None:
    asyncio.run(stream_trades())
