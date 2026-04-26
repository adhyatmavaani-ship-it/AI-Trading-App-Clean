from __future__ import annotations

import asyncio
import json
import logging

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
        async for message in socket:
            payload = json.loads(message)
            stream = payload["stream"]
            data = payload["data"]
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


def run() -> None:
    asyncio.run(stream_trades())
