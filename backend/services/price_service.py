from __future__ import annotations

from collections.abc import Iterable
import time

import httpx


class PriceService:
    def __init__(
        self,
        *,
        base_url: str = "https://api.binance.com",
        secondary_base_url: str | None = "https://api.bybit.com",
        timeout_seconds: float = 5.0,
        cache_max_age_seconds: float = 10.0,
        mismatch_threshold_pct: float = 0.002,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._secondary_base_url = secondary_base_url.rstrip("/") if secondary_base_url else None
        self._timeout = httpx.Timeout(timeout_seconds)
        self._cache_max_age_seconds = max(float(cache_max_age_seconds), 0.0)
        self._mismatch_threshold_pct = max(float(mismatch_threshold_pct), 0.0)
        self._cache: dict[str, tuple[float, float]] = {}

    def update_cache(self, symbol: str, price: float) -> None:
        self._cache[symbol.strip().upper()] = (float(price), time.time())

    def get_cached(self, symbol: str, *, max_age: float | None = None) -> float | None:
        normalized_symbol = symbol.strip().upper()
        if normalized_symbol not in self._cache:
            return None
        price, timestamp = self._cache[normalized_symbol]
        age_limit = self._cache_max_age_seconds if max_age is None else max(float(max_age), 0.0)
        if time.time() - timestamp > age_limit:
            return None
        return price

    async def get_price(self, symbol: str) -> float:
        normalized_symbol = symbol.strip().upper()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(
                f"{self._base_url}/api/v3/ticker/price",
                params={"symbol": normalized_symbol},
            )
            response.raise_for_status()
            payload = response.json()
        return float(payload["price"])

    async def get_price_secondary(self, symbol: str) -> float:
        if not self._secondary_base_url:
            raise RuntimeError("secondary price source disabled")
        normalized_symbol = symbol.strip().upper()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(
                f"{self._secondary_base_url}/v5/market/tickers",
                params={"category": "linear", "symbol": normalized_symbol},
            )
            response.raise_for_status()
            payload = response.json()
        result = payload.get("result", {})
        entries = result.get("list", [])
        if not entries:
            raise ValueError(f"secondary source missing price for {normalized_symbol}")
        return float(entries[0]["lastPrice"])

    async def safe_get_price(self, symbol: str) -> tuple[float | None, str]:
        normalized_symbol = symbol.strip().upper()
        try:
            price = await self.get_price(normalized_symbol)
            self.update_cache(normalized_symbol, price)
            return price, "live"
        except Exception:
            cached = self.get_cached(normalized_symbol)
            if cached is not None:
                return cached, "cache"
            if self._secondary_base_url:
                try:
                    price = await self.get_price_secondary(normalized_symbol)
                    self.update_cache(normalized_symbol, price)
                    return price, "secondary"
                except Exception:
                    return None, "fail"
            return None, "fail"

    async def get_price_with_validation(self, symbol: str) -> tuple[float | None, str]:
        normalized_symbol = symbol.strip().upper()
        live_or_cached_price, source = await self.safe_get_price(normalized_symbol)

        secondary_price: float | None = None
        if self._secondary_base_url:
            try:
                secondary_price = await self.get_price_secondary(normalized_symbol)
                self.update_cache(normalized_symbol, secondary_price)
            except Exception:
                secondary_price = None

        if live_or_cached_price is not None and secondary_price is not None:
            baseline = abs(live_or_cached_price)
            diff = 0.0 if baseline <= 1e-8 else abs(live_or_cached_price - secondary_price) / baseline
            if diff > self._mismatch_threshold_pct:
                return None, "mismatch"
            return live_or_cached_price, source

        if live_or_cached_price is not None:
            return live_or_cached_price, source
        if secondary_price is not None:
            return secondary_price, "secondary"
        return None, "fail"

    async def get_prices(self, symbols: Iterable[str]) -> dict[str, tuple[float | None, str]]:
        prices: dict[str, tuple[float | None, str]] = {}
        for symbol in {item.strip().upper() for item in symbols if item and item.strip()}:
            prices[symbol] = await self.get_price_with_validation(symbol)
        return prices
