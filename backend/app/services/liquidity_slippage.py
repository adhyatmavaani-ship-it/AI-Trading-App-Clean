from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LiquiditySlippageEngine:
    """Estimates order impact and decides whether to split orders into execution chunks."""

    slippage_threshold_bps: float = 35.0
    max_chunks: int = 4
    chunk_delay_ms: int = 350

    def estimate(self, order_book: dict, side: str, quantity: float) -> dict:
        levels = order_book["asks"] if side == "BUY" else order_book["bids"]
        remaining = quantity
        consumed_notional = 0.0
        filled = 0.0
        best_price = float(levels[0]["price"]) if levels else 0.0
        for level in levels:
            tradable = min(remaining, float(level["qty"]))
            consumed_notional += tradable * float(level["price"])
            filled += tradable
            remaining -= tradable
            if remaining <= 1e-8:
                break
        avg_price = consumed_notional / max(filled, 1e-8)
        slippage_bps = abs(avg_price - best_price) / max(best_price, 1e-8) * 10_000 if best_price else 0.0
        chunks = 1
        if slippage_bps > self.slippage_threshold_bps:
            chunks = min(self.max_chunks, max(2, int(slippage_bps // self.slippage_threshold_bps) + 1))
        chunk_quantity = quantity / chunks if chunks else quantity
        return {
            "estimated_slippage_bps": slippage_bps,
            "avg_execution_price": avg_price if avg_price else best_price,
            "chunks": chunks,
            "chunk_quantity": chunk_quantity,
            "chunk_delay_ms": self.chunk_delay_ms if chunks > 1 else 0,
        }
