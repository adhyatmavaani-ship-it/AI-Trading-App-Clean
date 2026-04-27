from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Protocol

import pandas as pd

from app.core.config import Settings

logger = logging.getLogger(__name__)


class ExchangeAdapter(Protocol):
    exchange_id: str

    def fetch_ticker_price(self, symbol: str) -> float:
        ...

    def fetch_symbol_rules(self, symbol: str) -> dict[str, float]:
        ...

    def create_order(
        self,
        *,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        limit_price: float | None = None,
    ) -> dict:
        ...

    def fetch_order(self, *, symbol: str, order_id: str) -> dict:
        ...

    def fetch_order_book(self, *, symbol: str, limit: int = 20) -> dict:
        ...

    def fetch_ohlcv(self, *, symbol: str, interval: str, limit: int = 300) -> pd.DataFrame:
        ...


@dataclass
class CcxtExchangeAdapter:
    settings: Settings
    exchange_id: str
    public_only: bool = False

    def __post_init__(self) -> None:
        import ccxt

        exchange_cls = getattr(ccxt, self.exchange_id)
        self.client = exchange_cls(self._client_config())
        if self.exchange_id == "binance" and self.settings.binance_testnet and hasattr(self.client, "set_sandbox_mode"):
            self.client.set_sandbox_mode(True)
        self.client.load_markets()

    def fetch_ticker_price(self, symbol: str) -> float:
        ticker = self.client.fetch_ticker(self._exchange_symbol(symbol))
        price = ticker.get("last") or ticker.get("close") or ticker.get("bid") or ticker.get("ask")
        if price is None:
            raise ValueError(f"{self.exchange_id} did not return a usable ticker price for {symbol}")
        return float(price)

    def fetch_symbol_rules(self, symbol: str) -> dict[str, float]:
        market = self.client.market(self._exchange_symbol(symbol))
        amount_limits = market.get("limits", {}).get("amount", {})
        cost_limits = market.get("limits", {}).get("cost", {})
        precision = market.get("precision", {})
        return {
            "min_qty": float(amount_limits.get("min") or 0.0),
            "max_qty": float(amount_limits.get("max") or 0.0) or float("inf"),
            "step_size": self._precision_step(precision.get("amount")),
            "tick_size": self._precision_step(precision.get("price")),
            "min_notional": float(cost_limits.get("min") or self.settings.exchange_min_notional),
        }

    def create_order(
        self,
        *,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        limit_price: float | None = None,
    ) -> dict:
        order = self.client.create_order(
            self._exchange_symbol(symbol),
            order_type.lower(),
            side.lower(),
            quantity,
            limit_price if order_type.upper() == "LIMIT" else None,
        )
        return self._normalize_order(order)

    def fetch_order(self, *, symbol: str, order_id: str) -> dict:
        order = self.client.fetch_order(id=str(order_id), symbol=self._exchange_symbol(symbol))
        return self._normalize_order(order)

    def fetch_order_book(self, *, symbol: str, limit: int = 20) -> dict:
        order_book = self.client.fetch_order_book(self._exchange_symbol(symbol), limit=limit)
        return {
            "bids": [{"price": float(price), "qty": float(qty)} for price, qty in order_book.get("bids", [])],
            "asks": [{"price": float(price), "qty": float(qty)} for price, qty in order_book.get("asks", [])],
        }

    def fetch_ohlcv(self, *, symbol: str, interval: str, limit: int = 300) -> pd.DataFrame:
        rows = self.client.fetch_ohlcv(self._exchange_symbol(symbol), timeframe=interval, limit=limit)
        if not rows:
            return pd.DataFrame()
        normalized_rows = []
        for row in rows:
            open_time, open_price, high, low, close, volume = row[:6]
            close_time = int(open_time) + self._interval_ms(interval) - 1
            normalized_rows.append(
                [
                    open_time,
                    open_price,
                    high,
                    low,
                    close,
                    volume,
                    close_time,
                    float(volume) * float(close),
                    0,
                    float(volume) * 0.5,
                    float(volume) * float(close) * 0.5,
                    0,
                ]
            )
        frame = pd.DataFrame(
            normalized_rows,
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
        for column in ("open", "high", "low", "close", "volume"):
            frame[column] = frame[column].astype(float)
        return frame

    def _client_config(self) -> dict:
        config = {"enableRateLimit": True}
        if self.public_only:
            return config
        if self.exchange_id == "binance":
            if self.settings.binance_api_key:
                config["apiKey"] = self.settings.binance_api_key
            if self.settings.binance_api_secret:
                config["secret"] = self.settings.binance_api_secret
        elif self.exchange_id == "kraken":
            if self.settings.kraken_api_key:
                config["apiKey"] = self.settings.kraken_api_key
            if self.settings.kraken_api_secret:
                config["secret"] = self.settings.kraken_api_secret
        elif self.exchange_id == "coinbase":
            if self.settings.coinbase_api_key:
                config["apiKey"] = self.settings.coinbase_api_key
            if self.settings.coinbase_api_secret:
                config["secret"] = self.settings.coinbase_api_secret
            if self.settings.coinbase_api_passphrase:
                config["password"] = self.settings.coinbase_api_passphrase
        return config

    def _exchange_symbol(self, symbol: str) -> str:
        normalized = str(symbol).upper().replace("-", "/")
        if "/" in normalized:
            return normalized
        for quote in self.settings.supported_quote_assets:
            if normalized.endswith(quote):
                base = normalized[: -len(quote)]
                if base:
                    return f"{base}/{quote}"
        return f"{normalized[:-len(self.settings.default_quote_asset)]}/{self.settings.default_quote_asset}"

    def _normalize_order(self, order: dict) -> dict:
        status = str(order.get("status", "unknown")).lower()
        filled = float(order.get("filled") or 0.0)
        amount = float(order.get("amount") or 0.0)
        average_price = float(order.get("average") or order.get("price") or 0.0)
        cost = float(order.get("cost") or (filled * average_price) or 0.0)
        mapped_status = "NEW"
        if status in {"closed", "filled"}:
            mapped_status = "FILLED"
        elif status == "open":
            mapped_status = "PARTIALLY_FILLED" if filled > 0 else "NEW"
        elif status in {"canceled", "cancelled"}:
            mapped_status = "CANCELED"
        elif status in {"rejected", "expired"}:
            mapped_status = status.upper()
        fee_paid = 0.0
        if order.get("fee"):
            fee_paid += float(order["fee"].get("cost") or 0.0)
        for fee in order.get("fees", []) or []:
            fee_paid += float(fee.get("cost") or 0.0)
        normalized = {
            "orderId": str(order.get("id", "")),
            "status": mapped_status,
            "executedQty": f"{filled:.8f}",
            "origQty": f"{amount:.8f}",
            "cummulativeQuoteQty": f"{cost:.8f}",
            "price": f"{average_price:.8f}",
            "fills": [{"price": f"{average_price:.8f}", "qty": f"{filled:.8f}"}] if filled > 0 and average_price > 0 else [],
            "exchange": self.exchange_id,
            "feePaid": fee_paid,
        }
        return normalized

    def _precision_step(self, raw_precision: int | float | None) -> float:
        if raw_precision is None:
            return 0.00000001
        if isinstance(raw_precision, int):
            return 10 ** (-raw_precision)
        return float(raw_precision)

    def _interval_ms(self, interval: str) -> int:
        mapping = {
            "1m": 60_000,
            "5m": 300_000,
            "15m": 900_000,
            "1h": 3_600_000,
        }
        return mapping.get(interval, 300_000)
