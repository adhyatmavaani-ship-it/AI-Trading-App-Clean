from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import time
from uuid import uuid4

from app.core.config import Settings
from app.services.liquidity_slippage import LiquiditySlippageEngine
from app.services.market_data import MarketDataService
from app.services.multi_chain_router import MultiChainRouter


@dataclass
class PaperExecutionEngine:
    settings: Settings
    market_data: MarketDataService

    def __post_init__(self) -> None:
        self.slippage_engine = LiquiditySlippageEngine(
            slippage_threshold_bps=float(self.settings.max_slippage_bps),
            chunk_delay_ms=self.settings.execution_chunk_delay_ms,
        )
        self.router = MultiChainRouter(self.settings)

    async def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str,
        limit_price: float | None = None,
        order_book: dict | None = None,
    ) -> dict:
        route = self.router.route(symbol, side, quantity)
        market_price = await self.market_data.fetch_latest_price(symbol)
        if route["broadcast_delay_ms"]:
            await asyncio.sleep(route["broadcast_delay_ms"] / 1000)
        half_spread_bps = self.settings.slippage_bps + self.settings.paper_fill_noise_bps
        signed_slippage = half_spread_bps / 10_000
        chunk_count = 1
        if order_book:
            plan = self.slippage_engine.estimate(order_book, side, quantity)
            chunk_count = plan["chunks"]
            half_spread_bps = max(half_spread_bps, plan["estimated_slippage_bps"])
        executed_price = market_price * (1 + signed_slippage if side == "BUY" else 1 - signed_slippage)
        if order_type == "LIMIT" and limit_price is not None:
            price_crossed = side == "BUY" and limit_price >= market_price
            price_crossed = price_crossed or (side == "SELL" and limit_price <= market_price)
            if price_crossed:
                executed_price = min(limit_price, executed_price) if side == "BUY" else max(limit_price, executed_price)
            else:
                return {
                    "orderId": str(uuid4()),
                    "status": "NEW",
                    "price": f"{limit_price:.8f}",
                    "executedQty": "0",
                    "origQty": f"{quantity:.8f}",
                    "fills": [],
                    "mode": "paper",
                    "filledRatio": 0.0,
                    "feePaid": 0.0,
                    "slippageBps": float(half_spread_bps),
                    "transactTime": int(datetime.now(timezone.utc).timestamp() * 1000),
                }
        fee_rate = self.settings.taker_fee_bps / 10_000
        filled_ratio = 0.65 if order_type == "LIMIT" else 1.0
        executed_qty = quantity * filled_ratio
        fee_paid = executed_price * executed_qty * fee_rate
        return {
            "orderId": str(uuid4()),
            "status": "FILLED" if filled_ratio == 1.0 else "PARTIALLY_FILLED",
            "price": f"{executed_price:.8f}",
            "executedQty": f"{executed_qty:.8f}",
            "origQty": f"{quantity:.8f}",
            "fills": [{"price": f"{executed_price:.8f}", "qty": f"{executed_qty:.8f}"}],
            "mode": "paper",
            "filledRatio": filled_ratio,
            "feePaid": fee_paid,
            "slippageBps": float(half_spread_bps),
            "executionLatencyMs": float(route["broadcast_delay_ms"]),
            "chunkCount": chunk_count,
            "transactTime": int(datetime.now(timezone.utc).timestamp() * 1000),
        }

