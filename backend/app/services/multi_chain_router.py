from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from app.core.config import Settings


@dataclass
class MultiChainRouter:
    settings: Settings

    def resolve_chain(self, symbol: str) -> str:
        symbol_upper = symbol.upper()
        if symbol_upper.endswith("SOL"):
            return "solana"
        if symbol_upper.startswith("BASE") or symbol_upper.endswith("BASE"):
            return "base"
        return "ethereum"

    def route(self, symbol: str, side: str, notional: float) -> dict:
        chain = self.resolve_chain(symbol)
        gas_estimate = {"ethereum": 18.0, "solana": 0.002, "base": 0.35}[chain]
        private_relay = bool(self.settings.private_rpc_url or self.settings.transaction_relay_url)
        route_start = perf_counter()
        if chain == "solana":
            relay_strategy = "jito" if self.settings.transaction_relay_url else "public"
            priority_fee = 50_000 if relay_strategy == "jito" else 10_000
            bundle_enabled = relay_strategy == "jito"
        else:
            relay_strategy = "flashbots" if private_relay else "public"
            priority_fee = 2 if relay_strategy == "flashbots" else 1
            bundle_enabled = relay_strategy == "flashbots"
        return {
            "chain": chain,
            "side": side,
            "notional": notional,
            "gas_estimate": gas_estimate,
            "bridge_required": False,
            "private_relay": relay_strategy in {"flashbots", "jito"},
            "relay_strategy": relay_strategy,
            "bundle_enabled": bundle_enabled,
            "priority_fee": priority_fee,
            "broadcast_delay_ms": 120 if relay_strategy in {"flashbots", "jito"} else 0,
            "routing_latency_ms": round((perf_counter() - route_start) * 1000, 2),
        }
