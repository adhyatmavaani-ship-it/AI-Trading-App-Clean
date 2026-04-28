from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import logging

import numpy as np
import pandas as pd

from app.core.config import Settings
from app.services.exchange_adapters import CcxtExchangeAdapter, ExchangeAdapter
from app.services.redis_cache import RedisCache

logger = logging.getLogger(__name__)


@dataclass
class MarketDataService:
    settings: Settings
    cache: RedisCache

    def __post_init__(self) -> None:
        self.exchange_clients: dict[str, ExchangeAdapter] = {}
        self.exchange_status: dict[str, dict[str, object]] = {}
        self.last_fetch_details: dict[str, dict[str, object]] = {}
        self._last_init_attempt_at: datetime | None = None
        self._ensure_exchange_clients(force=True)

    def diagnostics(self) -> dict[str, object]:
        configured = self._configured_exchanges()
        active = sorted(self.exchange_clients.keys())
        mode = str(self.settings.market_data_mode).lower()
        resolved_mode = "simulated" if mode == "simulated" or not active else "exchange"
        return {
            "configured_mode": mode,
            "resolved_mode": resolved_mode,
            "configured_exchanges": configured,
            "active_exchanges": active,
            "exchange_status": self.exchange_status,
            "using_mock_data": resolved_mode == "simulated",
            "last_init_attempt_at": self._isoformat(self._last_init_attempt_at),
            "retry_seconds": float(self.settings.market_data_exchange_retry_seconds),
            "last_fetch_details": self.last_fetch_details,
            "force_execution_override_enabled": bool(self.settings.force_execution_override_enabled),
            "force_execution_override_confidence_floor": float(self.settings.force_execution_override_confidence_floor),
        }

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

    def inject_test_market_move(
        self,
        symbol: str,
        *,
        change: float,
        volume_multiplier: float = 3.0,
        intervals: tuple[str, ...] = ("1m", "5m", "15m", "1h"),
    ) -> dict[str, object]:
        normalized_symbol = str(symbol or "").upper().strip()
        if not normalized_symbol:
            raise ValueError("symbol is required")
        reference_price = (
            self.latest_stream_price(normalized_symbol)
            or self._latest_cached_close(normalized_symbol)
            or self._mock_latest_price(normalized_symbol)
        )
        updated_price = max(1e-8, float(reference_price) * (1.0 + float(change)))
        timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        self.cache.set_json(
            f"stream:{normalized_symbol.lower()}@trade",
            {"p": updated_price, "T": timestamp_ms},
            ttl=self.settings.market_data_cache_ttl,
        )
        order_book = self._mock_order_book(updated_price)
        self.cache.set_json(
            f"stream:book:{normalized_symbol}",
            {
                "best_bid": float(order_book["bids"][0]["price"]),
                "best_bid_qty": float(order_book["bids"][0]["qty"]),
                "best_ask": float(order_book["asks"][0]["price"]),
                "best_ask_qty": float(order_book["asks"][0]["qty"]),
                "updated_at": timestamp_ms,
            },
            ttl=self.settings.market_data_cache_ttl,
        )
        updated_intervals: dict[str, int] = {}
        for interval in intervals:
            frame = self._load_cached_frame(normalized_symbol, interval)
            if frame.empty:
                frame = self._mock_ohlcv_frame(symbol=normalized_symbol, interval=interval)
            mutated = self._apply_test_move_to_frame(
                frame=frame,
                updated_price=updated_price,
                volume_multiplier=volume_multiplier,
            )
            self.cache.set_json(
                f"ohlcv:{normalized_symbol}:{interval}",
                {"rows": mutated.to_dict(orient="records")},
                ttl=self.settings.market_data_cache_ttl,
            )
            self._remember_fetch("ohlcv", normalized_symbol, "test_override", interval=interval, rows=len(mutated))
            updated_intervals[interval] = int(len(mutated))
        self._remember_fetch("price", normalized_symbol, "test_override")
        self._remember_fetch("order_book", normalized_symbol, "test_override")
        return {
            "symbol": normalized_symbol,
            "reference_price": round(float(reference_price), 8),
            "updated_price": round(float(updated_price), 8),
            "change": round(float(change), 8),
            "volume_multiplier": round(float(volume_multiplier), 8),
            "updated_intervals": updated_intervals,
        }

    async def fetch_latest_price(self, symbol: str) -> float:
        self._ensure_exchange_clients()
        cached_price = self.latest_stream_price(symbol)
        if cached_price is not None:
            self._remember_fetch("price", symbol, "stream")
            return cached_price
        for exchange_id, client in list(self.exchange_clients.items()):
            try:
                price = await asyncio.to_thread(client.fetch_ticker_price, symbol)
                self._remember_fetch("price", symbol, f"exchange:{exchange_id}")
                return price
            except Exception as exc:
                self._record_exchange_failure(exchange_id, exc)
                logger.warning(
                    "market_data_price_fallback",
                    extra={"event": "market_data_price_fallback", "context": {"symbol": symbol, "exchange": exchange_id}},
                )
        self._remember_fetch("price", symbol, "simulated")
        return self._mock_latest_price(symbol)

    async def fetch_market_tickers(
        self,
        *,
        quote_asset: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        self._ensure_exchange_clients()
        normalized_quote = str(quote_asset or "").upper().strip()
        cache_key = f"market:tickers:{normalized_quote or 'ALL'}"
        cached = self.cache.get_json(cache_key) or {}
        cached_items = cached.get("items") or []
        if cached_items:
            self._remember_fetch("market_tickers", normalized_quote or "ALL", "cache")
            items = [dict(item) for item in cached_items]
            return items[:limit] if limit is not None else items
        for exchange_id, client in list(self.exchange_clients.items()):
            try:
                rows = await asyncio.to_thread(client.fetch_tickers)
                filtered = [
                    row
                    for row in rows
                    if not normalized_quote or str(row.get("quote", "")).upper() == normalized_quote
                ]
                filtered.sort(
                    key=lambda item: float(item.get("quote_volume", 0.0) or 0.0),
                    reverse=True,
                )
                self.cache.set_json(
                    cache_key,
                    {"items": filtered},
                    self.settings.market_data_cache_ttl,
                )
                self._remember_fetch("market_tickers", normalized_quote or "ALL", f"exchange:{exchange_id}")
                return filtered[:limit] if limit is not None else filtered
            except Exception as exc:
                self._record_exchange_failure(exchange_id, exc)
                logger.warning(
                    "market_data_tickers_exchange_failed",
                    extra={"event": "market_data_tickers_exchange_failed", "context": {"exchange": exchange_id}},
                )
        simulated = self._mock_market_tickers(quote_asset=normalized_quote or self.settings.default_quote_asset)
        self.cache.set_json(cache_key, {"items": simulated}, self.settings.market_data_cache_ttl)
        self._remember_fetch("market_tickers", normalized_quote or "ALL", "simulated")
        return simulated[:limit] if limit is not None else simulated

    async def fetch_multi_timeframe_ohlcv(
        self, symbol: str, intervals: tuple[str, ...] = ("1m", "5m", "15m")
    ) -> dict[str, pd.DataFrame]:
        self._ensure_exchange_clients()
        results = {}
        pending_intervals: list[str] = []
        for interval in intervals:
            cache_key = f"ohlcv:{symbol}:{interval}"
            cached = self.cache.get_json(cache_key)
            if cached:
                frame = pd.DataFrame(cached["rows"])
                if not frame.empty and not self._frame_is_stale(frame, interval):
                    results[interval] = frame
                    self._remember_fetch("ohlcv", symbol, "cache", interval=interval)
                else:
                    pending_intervals.append(interval)
            else:
                pending_intervals.append(interval)

        for interval in pending_intervals:
            frame, source = await self._fetch_ohlcv_with_fallback(symbol=symbol, interval=interval)
            if frame.empty or self._frame_is_stale(frame, interval):
                logger.warning(
                    "market_data_ohlcv_fallback",
                    extra={
                        "event": "market_data_ohlcv_fallback",
                        "context": {"symbol": symbol, "interval": interval},
                    },
                )
                frame = self._mock_ohlcv_frame(symbol=symbol, interval=interval)
                source = "simulated"
            results[interval] = frame
            self._remember_fetch("ohlcv", symbol, source, interval=interval, rows=len(frame))
            self.cache.set_json(
                f"ohlcv:{symbol}:{interval}",
                {"rows": frame.to_dict(orient="records")},
                self.settings.market_data_cache_ttl,
            )
        return results

    async def fetch_order_book(self, symbol: str) -> dict:
        self._ensure_exchange_clients()
        cached_book = self.latest_stream_order_book(symbol)
        if cached_book is not None:
            self._remember_fetch("order_book", symbol, "stream")
            return cached_book
        for exchange_id, client in list(self.exchange_clients.items()):
            try:
                order_book = await asyncio.to_thread(client.fetch_order_book, symbol=symbol, limit=20)
                self._remember_fetch("order_book", symbol, f"exchange:{exchange_id}")
                return order_book
            except Exception as exc:
                self._record_exchange_failure(exchange_id, exc)
                logger.warning(
                    "market_data_order_book_fallback",
                    extra={"event": "market_data_order_book_fallback", "context": {"symbol": symbol, "exchange": exchange_id}},
                )
        self._remember_fetch("order_book", symbol, "simulated")
        return self._mock_order_book(self._mock_latest_price(symbol))

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

    def _mock_latest_price(self, symbol: str) -> float:
        symbol_key = str(symbol).upper()
        defaults = {
            "BTCUSDT": 68000.0,
            "ETHUSDT": 3200.0,
            "SOLUSDT": 145.0,
        }
        if symbol_key in defaults:
            return defaults[symbol_key]
        return 100.0 + float(abs(hash(symbol_key)) % 1000)

    def _mock_market_tickers(self, *, quote_asset: str) -> list[dict[str, object]]:
        items: list[dict[str, object]] = []
        for index, symbol in enumerate(self.settings.market_universe_symbols or self.settings.websocket_symbols):
            normalized_symbol = str(symbol).upper().strip()
            if not normalized_symbol.endswith(quote_asset):
                continue
            price = self._latest_cached_close(normalized_symbol) or self._mock_latest_price(normalized_symbol)
            change_pct = ((index % 7) - 3) * 0.85
            quote_volume = max(1_000_000.0, 12_000_000.0 - (index * 420_000.0))
            items.append(
                {
                    "symbol": normalized_symbol,
                    "base": normalized_symbol[: -len(quote_asset)],
                    "quote": quote_asset,
                    "price": round(float(price), 8),
                    "change_pct": round(float(change_pct), 4),
                    "base_volume": round(float(quote_volume / max(price, 1e-8)), 8),
                    "quote_volume": round(float(quote_volume), 4),
                    "exchange": "simulated",
                }
            )
        items.sort(key=lambda item: float(item.get("quote_volume", 0.0) or 0.0), reverse=True)
        return items

    def _latest_cached_close(self, symbol: str) -> float | None:
        normalized_symbol = str(symbol or "").upper().strip()
        for interval in ("1m", "5m", "15m", "1h"):
            frame = self._load_cached_frame(normalized_symbol, interval)
            if frame.empty or "close" not in frame.columns:
                continue
            try:
                return float(frame["close"].astype(float).iloc[-1])
            except Exception:
                continue
        return None

    def _load_cached_frame(self, symbol: str, interval: str) -> pd.DataFrame:
        cached = self.cache.get_json(f"ohlcv:{symbol}:{interval}") or {}
        rows = cached.get("rows") or []
        return pd.DataFrame(rows)

    def _apply_test_move_to_frame(
        self,
        *,
        frame: pd.DataFrame,
        updated_price: float,
        volume_multiplier: float,
    ) -> pd.DataFrame:
        if frame.empty:
            return frame
        mutated = frame.copy()
        numeric_columns = [column for column in ("open", "high", "low", "close", "volume") if column in mutated.columns]
        for column in numeric_columns:
            mutated[column] = mutated[column].astype(float)
        last_index = mutated.index[-1]
        previous_close = float(mutated["close"].iloc[-2] if len(mutated) > 1 else mutated["close"].iloc[-1])
        candle_open = previous_close
        candle_close = float(updated_price)
        candle_high = max(candle_open, candle_close) * 1.001
        candle_low = min(candle_open, candle_close) * 0.999
        baseline_volume = float(mutated["volume"].tail(min(len(mutated), 20)).mean() or 1.0)
        mutated.at[last_index, "open"] = candle_open
        mutated.at[last_index, "high"] = candle_high
        mutated.at[last_index, "low"] = candle_low
        mutated.at[last_index, "close"] = candle_close
        mutated.at[last_index, "volume"] = max(1.0, baseline_volume * float(volume_multiplier))
        if "quote_volume" in mutated.columns:
            mutated["quote_volume"] = mutated["quote_volume"].astype(float)
            mutated.at[last_index, "quote_volume"] = mutated.at[last_index, "volume"] * candle_close
        if "taker_base" in mutated.columns:
            mutated["taker_base"] = mutated["taker_base"].astype(float)
            mutated.at[last_index, "taker_base"] = mutated.at[last_index, "volume"] * 0.55
        if "taker_quote" in mutated.columns:
            mutated["taker_quote"] = mutated["taker_quote"].astype(float)
            mutated.at[last_index, "taker_quote"] = mutated.at[last_index, "volume"] * candle_close * 0.55
        if "close_time" in mutated.columns:
            mutated["close_time"] = mutated["close_time"].astype(float)
            interval_ms = 60_000
            if "open_time" in mutated.columns:
                mutated["open_time"] = mutated["open_time"].astype(float)
                if len(mutated) > 1:
                    interval_ms = int(mutated["open_time"].iloc[-1] - mutated["open_time"].iloc[-2]) or interval_ms
                now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
                mutated.at[last_index, "open_time"] = now_ms - interval_ms
                mutated.at[last_index, "close_time"] = now_ms - 1
            elif len(mutated) > 1:
                interval_ms = int(mutated["close_time"].iloc[-1] - mutated["close_time"].iloc[-2]) or interval_ms
                mutated.at[last_index, "close_time"] = int(datetime.now(timezone.utc).timestamp() * 1000) - 1
        return mutated

    async def _fetch_ohlcv_with_fallback(self, *, symbol: str, interval: str) -> tuple[pd.DataFrame, str]:
        for exchange_id, client in list(self.exchange_clients.items()):
            try:
                frame = await asyncio.to_thread(client.fetch_ohlcv, symbol=symbol, interval=interval, limit=300)
                return frame, f"exchange:{exchange_id}"
            except Exception as exc:
                self._record_exchange_failure(exchange_id, exc)
                logger.warning(
                    "market_data_ohlcv_exchange_failed",
                    extra={"event": "market_data_ohlcv_exchange_failed", "context": {"symbol": symbol, "interval": interval, "exchange": exchange_id}},
                )
        return pd.DataFrame(), "simulated"

    def _configured_exchanges(self) -> list[str]:
        ordered = [self.settings.primary_exchange, *self.settings.backup_exchanges]
        unique: list[str] = []
        for exchange_id in ordered:
            normalized = str(exchange_id).strip().lower()
            if normalized and normalized not in unique:
                unique.append(normalized)
        return unique

    def _ensure_exchange_clients(self, *, force: bool = False) -> None:
        mode = str(self.settings.market_data_mode).lower()
        if mode == "simulated":
            for exchange_id in self._configured_exchanges():
                self.exchange_status[exchange_id] = {
                    "status": "simulated",
                    "last_error": None,
                    "last_attempt_at": self._isoformat(datetime.now(timezone.utc)),
                    "last_success_at": None,
                }
            return

        now = datetime.now(timezone.utc)
        if (
            not force
            and self._last_init_attempt_at is not None
            and (now - self._last_init_attempt_at).total_seconds() < float(self.settings.market_data_exchange_retry_seconds)
        ):
            return
        self._last_init_attempt_at = now

        for exchange_id in self._configured_exchanges():
            status = self.exchange_status.setdefault(
                exchange_id,
                {"status": "pending", "last_error": None, "last_attempt_at": None, "last_success_at": None},
            )
            status["last_attempt_at"] = self._isoformat(now)
            if exchange_id in self.exchange_clients:
                status["status"] = "active"
                status["last_error"] = None
                if status.get("last_success_at") is None:
                    status["last_success_at"] = self._isoformat(now)
                continue
            try:
                self.exchange_clients[exchange_id] = CcxtExchangeAdapter(self.settings, exchange_id, public_only=True)
                status["status"] = "active"
                status["last_error"] = None
                status["last_success_at"] = self._isoformat(now)
            except Exception as exc:
                status["status"] = "failed"
                status["last_error"] = str(exc)[:200]
                logger.warning(
                    "market_data_exchange_init_failed",
                    extra={"event": "market_data_exchange_init_failed", "context": {"exchange": exchange_id, "error": str(exc)[:200]}},
                )

    def _record_exchange_failure(self, exchange_id: str, exc: Exception) -> None:
        now = datetime.now(timezone.utc)
        status = self.exchange_status.setdefault(
            exchange_id,
            {"status": "failed", "last_error": None, "last_attempt_at": None, "last_success_at": None},
        )
        status["status"] = "failed"
        status["last_error"] = str(exc)[:200]
        status["last_attempt_at"] = self._isoformat(now)
        self.exchange_clients.pop(exchange_id, None)

    def _remember_fetch(
        self,
        fetch_type: str,
        symbol: str,
        source: str,
        *,
        interval: str | None = None,
        rows: int | None = None,
    ) -> None:
        key = f"{fetch_type}:{str(symbol).upper()}"
        if interval is not None:
            key = f"{key}:{interval}"
        payload: dict[str, object] = {
            "source": source,
            "updated_at": self._isoformat(datetime.now(timezone.utc)),
        }
        if interval is not None:
            payload["interval"] = interval
        if rows is not None:
            payload["rows"] = int(rows)
        self.last_fetch_details[key] = payload

    def _isoformat(self, value: datetime | None) -> str | None:
        return value.isoformat() if value is not None else None
