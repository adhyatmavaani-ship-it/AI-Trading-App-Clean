from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, getcontext


getcontext().prec = 28


@dataclass
class AllocationEngine:
    precision: int = 8

    def allocate(
        self,
        intents: list[dict],
        executed_quantity: float,
        fee_paid: float,
        executed_price: float,
        aggregate_order_id: str,
        aggregate_status: str,
    ) -> list[dict]:
        if not intents:
            return []
        quantum = Decimal("1").scaleb(-self.precision)
        total_requested = sum(Decimal(str(intent["requested_quantity"])) for intent in intents)
        executed = Decimal(str(executed_quantity))
        if total_requested <= 0 or executed <= 0:
            return [
                {
                    **intent,
                    "aggregate_order_id": aggregate_order_id,
                    "allocated_quantity": 0.0,
                    "remaining_quantity": float(intent["requested_quantity"]),
                    "fill_ratio": 0.0,
                    "fee_paid": 0.0,
                    "executed_price": executed_price,
                    "allocation_status": "FAILED" if aggregate_status in {"FAILED", "REJECTED"} else "UNFILLED",
                }
                for intent in intents
            ]

        provisional: list[dict] = []
        allocated_sum = Decimal("0")
        for intent in intents:
            requested = Decimal(str(intent["requested_quantity"]))
            exact = (executed * requested) / total_requested
            rounded = exact.quantize(quantum, rounding=ROUND_DOWN)
            provisional.append(
                {
                    "intent": intent,
                    "requested": requested,
                    "allocated": rounded,
                    "remainder_rank": exact - rounded,
                }
            )
            allocated_sum += rounded

        remainder = (executed - allocated_sum).quantize(quantum)
        remainder_units = int((remainder / quantum).to_integral_value()) if remainder > 0 else 0
        ranked = sorted(
            range(len(provisional)),
            key=lambda idx: (
                provisional[idx]["remainder_rank"],
                provisional[idx]["requested"],
                str(provisional[idx]["intent"].get("user_id", "")),
            ),
            reverse=True,
        )
        for idx in ranked[:remainder_units]:
            provisional[idx]["allocated"] += quantum

        fee_total = Decimal(str(fee_paid))
        fee_allocated_sum = Decimal("0")
        allocations: list[dict] = []
        fee_provisional: list[dict] = []
        for item in provisional:
            ratio = item["allocated"] / executed if executed > 0 else Decimal("0")
            fee_exact = fee_total * ratio
            fee_rounded = fee_exact.quantize(quantum, rounding=ROUND_DOWN)
            fee_provisional.append({"exact": fee_exact, "rounded": fee_rounded})
            fee_allocated_sum += fee_rounded

        fee_remainder = (fee_total - fee_allocated_sum).quantize(quantum)
        fee_remainder_units = int((fee_remainder / quantum).to_integral_value()) if fee_remainder > 0 else 0
        fee_ranked = sorted(
            range(len(provisional)),
            key=lambda idx: fee_provisional[idx]["exact"] - fee_provisional[idx]["rounded"],
            reverse=True,
        )
        for idx in fee_ranked[:fee_remainder_units]:
            fee_provisional[idx]["rounded"] += quantum

        partial = executed < total_requested
        for idx, item in enumerate(provisional):
            intent = item["intent"]
            allocated = item["allocated"]
            requested = item["requested"]
            remaining = max(Decimal("0"), requested - allocated)
            fill_ratio = float((allocated / requested) if requested > 0 else Decimal("0"))
            if allocated <= 0:
                allocation_status = "FAILED" if aggregate_status in {"FAILED", "REJECTED"} else "UNFILLED"
            elif partial and allocated < requested:
                allocation_status = "PARTIALLY_FILLED"
            else:
                allocation_status = "FILLED"
            allocations.append(
                {
                    **intent,
                    "aggregate_order_id": aggregate_order_id,
                    "allocated_quantity": float(allocated),
                    "remaining_quantity": float(remaining),
                    "fill_ratio": fill_ratio,
                    "fee_paid": float(fee_provisional[idx]["rounded"]),
                    "executed_price": executed_price,
                    "allocation_status": allocation_status,
                }
            )
        return allocations
