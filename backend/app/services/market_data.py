from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx
import pandas as pd

from app.core.config import Settings
from app.services.redis_cache import RedisCache


@dataclass
class MarketDataService:
    settings: Settings
    cache: RedisCache

    def latest_stream_price(self, symbol: str) -> float | None:
        payload = self.cache.get_json(f"stream:{symbol.lower()}@trade")
        if payload and payload.get("p") is not None:
            return float(payload["p"])
        return None

    def latest_stream_order_book(self, symbol: str) -> dict | None:
        payload = self.cache.get_json(f"stream:book:{symbol.upper()}")
        if not payload:
            return None
        best_bid = float(payload.get("best_bid", 0.0))
        best_bid_qty = float(payload.get("best_bid_qty", 0.0))
        best_ask = float(payload.get("best_ask", 0.0))
        best_ask_qty = float(payload.get("best_ask_qty", 0.0))
        if best_bid <= 0 or best_ask <= 0:
            return None
        return {
            "bids": [{"price": best_bid, "qty": best_bid_qty}],
            "asks": [{"price": best_ask, "qty": best_ask_qty}],
        }

    async def fetch_latest_price(self, symbol: str) -> float:
        cached_price = self.latest_stream_price(symbol)
        if cached_price is not None:
            return cached_price
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                "https://api.binance.com/api/v3/ticker/price",
                params={"symbol": symbol},
            )
            response.raise_for_status()
            return float(response.json()["price"])

    async def fetch_multi_timeframe_ohlcv(
        self, symbol: str, intervals: tuple[str, ...] = ("1m", "5m", "15m")
    ) -> dict[str, pd.DataFrame]:
        async with httpx.AsyncClient(timeout=20) as client:
            results = {}
            pending_intervals: list[str] = []
            for interval in intervals:
                cache_key = f"ohlcv:{symbol}:{interval}"
                cached = self.cache.get_json(cache_key)
                if cached:
                    results[interval] = pd.DataFrame(cached["rows"])
                else:
                    pending_intervals.append(interval)

            if pending_intervals:
                responses = await asyncio.gather(
                    *[
                        client.get(
                            "https://api.binance.com/api/v3/klines",
                            params={"symbol": symbol, "interval": interval, "limit": 300},
                        )
                        for interval in pending_intervals
                    ]
                )
                for interval, response in zip(pending_intervals, responses, strict=False):
                    response.raise_for_status()
                    rows = response.json()
                    frame = pd.DataFrame(
                        rows,
                        columns=[
                            "open_time",
                            "open",
                            "high",
                            "low",
                            "close",
                            "volume",
                            "close_time",
                            "quote_volume",
                            "trades",
                            "taker_base",
                            "taker_quote",
                            "ignore",
                        ],
                    )
                    for col in ["open", "high", "low", "close", "volume"]:
                        frame[col] = frame[col].astype(float)
                    results[interval] = frame
                    self.cache.set_json(
                        f"ohlcv:{symbol}:{interval}",
                        {"rows": frame.to_dict(orient="records")},
                        self.settings.market_data_cache_ttl,
                    )
            return results

    async def fetch_order_book(self, symbol: str) -> dict:
        cached_book = self.latest_stream_order_book(symbol)
        if cached_book is not None:
            return cached_book
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                "https://api.binance.com/api/v3/depth",
                params={"symbol": symbol, "limit": 20},
            )
            response.raise_for_status()
            payload = response.json()
            return {
                "bids": [{"price": float(p), "qty": float(q)} for p, q in payload["bids"]],
                "asks": [{"price": float(p), "qty": float(q)} for p, q in payload["asks"]],
            }
