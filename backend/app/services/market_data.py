from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import logging

import httpx
import numpy as np
import pandas as pd

from app.core.config import Settings
from app.services.redis_cache import RedisCache

logger = logging.getLogger(__name__)


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
                    frame = pd.DataFrame(cached["rows"])
                    if not frame.empty and not self._frame_is_stale(frame, interval):
                        results[interval] = frame
                    else:
                        pending_intervals.append(interval)
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
                    ],
                    return_exceptions=True,
                )
                for interval, response in zip(pending_intervals, responses, strict=False):
                    frame = self._response_frame(response)
                    if frame.empty or self._frame_is_stale(frame, interval):
                        logger.warning(
                            "market_data_ohlcv_fallback",
                            extra={
                                "event": "market_data_ohlcv_fallback",
                                "context": {"symbol": symbol, "interval": interval},
                            },
                        )
                        frame = self._mock_ohlcv_frame(symbol=symbol, interval=interval)
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
            try:
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
            except Exception:
                logger.warning(
                    "market_data_order_book_fallback",
                    extra={"event": "market_data_order_book_fallback", "context": {"symbol": symbol}},
                )
                return self._mock_order_book(await self.fetch_latest_price(symbol))

    def _response_frame(self, response: object) -> pd.DataFrame:
        if isinstance(response, Exception):
            return pd.DataFrame()
        response.raise_for_status()
        rows = response.json()
        if not rows:
            return pd.DataFrame()
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
        return frame

    def _frame_is_stale(self, frame: pd.DataFrame, interval: str) -> bool:
        if frame.empty or "close_time" not in frame.columns:
            return True
        last_close_ms = float(frame["close_time"].iloc[-1])
        last_close = datetime.fromtimestamp(last_close_ms / 1000, tz=timezone.utc)
        max_age_seconds = {"1m": 180, "5m": 900, "15m": 2700, "1h": 7200}.get(interval, 900)
        return (datetime.now(timezone.utc) - last_close).total_seconds() > max_age_seconds

    def _mock_ohlcv_frame(self, *, symbol: str, interval: str, limit: int = 300) -> pd.DataFrame:
        seed = abs(hash(f"{symbol}:{interval}")) % (2**32)
        rng = np.random.default_rng(seed)
        base_price = self.latest_stream_price(symbol) or 100.0 + (abs(hash(symbol)) % 1000)
        interval_minutes = {"1m": 1, "5m": 5, "15m": 15, "1h": 60}.get(interval, 5)
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        step_ms = interval_minutes * 60 * 1000
        rows: list[list[float | int]] = []
        price = float(base_price)
        for idx in range(limit):
            open_time = now_ms - (limit - idx) * step_ms
            drift = np.sin(idx / 12) * 0.0015
            shock = float(rng.normal(0.0, 0.0025))
            close = max(1e-6, price * (1 + drift + shock))
            high = max(price, close) * (1 + abs(float(rng.normal(0.001, 0.0008))))
            low = min(price, close) * (1 - abs(float(rng.normal(0.001, 0.0008))))
            volume = max(1.0, float(rng.normal(1500.0, 400.0)))
            close_time = open_time + step_ms - 1
            rows.append([open_time, price, high, low, close, volume, close_time, volume * close, 120, volume * 0.52, volume * close * 0.52, 0])
            price = close
        return self._response_frame(type("MockResponse", (), {"raise_for_status": lambda self: None, "json": lambda self: rows})())

    def _mock_order_book(self, price: float) -> dict:
        spread = max(price * 0.0005, 0.01)
        return {
            "bids": [{"price": round(price - spread, 8), "qty": 25.0}],
            "asks": [{"price": round(price + spread, 8), "qty": 25.0}],
        }
