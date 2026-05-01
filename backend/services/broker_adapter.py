from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from uuid import uuid4


class BrokerAdapter(ABC):
    name = "broker"
    is_live = False

    @abstractmethod
    def place_order(
        self,
        *,
        symbol: str,
        side: str,
        quantity: float,
        sl: float,
        tp: float,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_position(self, symbol: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def close_position(self, symbol: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_open_positions(self) -> dict[str, dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def get_open_orders(self) -> dict[str, dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def get_order(self, order_id: str) -> dict[str, Any] | None:
        raise NotImplementedError


class PaperBroker(BrokerAdapter):
    name = "paper"
    is_live = False

    def __init__(self) -> None:
        self._positions: dict[str, dict[str, Any]] = {}
        self._open_orders: dict[str, dict[str, Any]] = {}
        self._orders: dict[str, dict[str, Any]] = {}

    def place_order(
        self,
        *,
        symbol: str,
        side: str,
        quantity: float,
        sl: float,
        tp: float,
    ) -> dict[str, Any]:
        broker_order_id = f"paper-{uuid4().hex[:12]}"
        normalized_symbol = symbol.upper()
        normalized_side = side.upper()
        order = {
            "status": "filled",
            "exchange_status": "filled",
            "exchange": self.name,
            "broker_order_id": broker_order_id,
            "symbol": normalized_symbol,
            "side": normalized_side,
            "qty": float(quantity),
            "sl": float(sl),
            "tp": float(tp),
            "executedQty": float(quantity),
            "avgPrice": 0.0,
        }
        self._orders[broker_order_id] = dict(order)
        self._positions[normalized_symbol] = {
            "symbol": normalized_symbol,
            "side": normalized_side,
            "qty": float(quantity),
            "avgPrice": 0.0,
            "status": "OPEN",
            "broker_order_id": broker_order_id,
        }
        return order

    def get_position(self, symbol: str) -> dict[str, Any]:
        return dict(self._positions.get(symbol.upper(), {"status": "flat", "symbol": symbol.upper()}))

    def close_position(self, symbol: str) -> dict[str, Any]:
        normalized_symbol = symbol.upper()
        position = self._positions.pop(normalized_symbol, None)
        if position is None:
            return {"status": "closed", "symbol": normalized_symbol}
        order_id = str(position.get("broker_order_id", ""))
        if order_id and order_id in self._orders:
            self._orders[order_id] = {
                **self._orders[order_id],
                "status": "FILLED",
                "exchange_status": "filled",
                "avgPrice": float(position.get("avgPrice") or 0.0),
                "executedQty": float(position.get("qty") or 0.0),
            }
        return {"status": "closed", "symbol": normalized_symbol}

    def get_open_positions(self) -> dict[str, dict[str, Any]]:
        return {symbol: dict(position) for symbol, position in self._positions.items()}

    def get_open_orders(self) -> dict[str, dict[str, Any]]:
        return {order_id: dict(order) for order_id, order in self._open_orders.items()}

    def get_order(self, order_id: str) -> dict[str, Any] | None:
        if not order_id:
            return None
        order = self._orders.get(str(order_id))
        return dict(order) if order is not None else None


class BinanceBroker(BrokerAdapter):
    name = "binance"
    is_live = True

    def __init__(self, *, base_url: str = "https://api.binance.com") -> None:
        self._base_url = base_url.rstrip("/")

    def place_order(
        self,
        *,
        symbol: str,
        side: str,
        quantity: float,
        sl: float,
        tp: float,
    ) -> dict[str, Any]:
        del sl, tp
        return {
            "status": "sent",
            "exchange_status": "sent",
            "exchange": self.name,
            "broker_order_id": f"binance-{uuid4().hex[:12]}",
            "symbol": symbol,
            "side": side,
            "qty": float(quantity),
            "base_url": self._base_url,
        }

    def get_position(self, symbol: str) -> dict[str, Any]:
        return {
            "status": "unknown",
            "exchange": self.name,
            "symbol": symbol.upper(),
        }

    def close_position(self, symbol: str) -> dict[str, Any]:
        return {
            "status": "sent",
            "exchange": self.name,
            "symbol": symbol.upper(),
        }

    def get_open_positions(self) -> dict[str, dict[str, Any]]:
        return {}

    def get_open_orders(self) -> dict[str, dict[str, Any]]:
        return {}

    def get_order(self, order_id: str) -> dict[str, Any] | None:
        if not order_id:
            return None
        return {
            "orderId": order_id,
            "status": "UNKNOWN",
            "exchange": self.name,
        }


def create_broker_adapter(config: dict[str, Any]) -> BrokerAdapter:
    mode = str(config.get("mode", "paper")).strip().lower()
    if mode == "paper":
        return PaperBroker()
    return BinanceBroker(base_url=str(config.get("binance_base_url", "https://api.binance.com")))
