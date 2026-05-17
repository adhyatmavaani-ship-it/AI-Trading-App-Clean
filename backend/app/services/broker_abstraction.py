from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class BrokerCapability:
    broker: str
    supports_bracket_orders: bool = False
    supports_reduce_only: bool = False
    supports_websocket_fills: bool = False
    supports_paper: bool = True
    max_order_rate_per_second: int = 1


@dataclass(frozen=True)
class UnifiedOrderRequest:
    symbol: str
    side: str
    quantity: float
    order_type: str = "MARKET"
    price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    client_order_id: str | None = None
    reduce_only: bool = False
    paper: bool = True
    metadata: dict[str, Any] | None = None


class BrokerAdapter(Protocol):
    name: str
    capability: BrokerCapability

    def normalize_order(self, request: UnifiedOrderRequest) -> dict[str, Any]:
        ...


class PaperBrokerAdapter:
    name = "paper"
    capability = BrokerCapability(
        broker="paper",
        supports_bracket_orders=True,
        supports_reduce_only=True,
        supports_websocket_fills=True,
        supports_paper=True,
        max_order_rate_per_second=100,
    )

    def normalize_order(self, request: UnifiedOrderRequest) -> dict[str, Any]:
        return {
            "broker": self.name,
            "symbol": request.symbol.upper(),
            "side": request.side.upper(),
            "quantity": float(request.quantity),
            "order_type": request.order_type.upper(),
            "price": request.price,
            "stop_loss": request.stop_loss,
            "take_profit": request.take_profit,
            "client_order_id": request.client_order_id,
            "reduce_only": bool(request.reduce_only),
            "paper": True,
            "metadata": request.metadata or {},
        }


class BrokerCapabilityRegistry:
    """Capability lookup only. It does not place or reroute live orders."""

    def __init__(self) -> None:
        self._adapters: dict[str, BrokerAdapter] = {}
        self.register(PaperBrokerAdapter())

    def register(self, adapter: BrokerAdapter) -> None:
        self._adapters[adapter.name.lower()] = adapter

    def capability(self, broker: str) -> BrokerCapability | None:
        adapter = self._adapters.get(str(broker or "").lower())
        return adapter.capability if adapter is not None else None

    def normalize(self, broker: str, request: UnifiedOrderRequest) -> dict[str, Any]:
        adapter = self._adapters.get(str(broker or "").lower())
        if adapter is None:
            raise ValueError(f"Unsupported broker adapter: {broker}")
        return adapter.normalize_order(request)

    def list_capabilities(self) -> list[dict[str, Any]]:
        return [adapter.capability.__dict__ for adapter in self._adapters.values()]
