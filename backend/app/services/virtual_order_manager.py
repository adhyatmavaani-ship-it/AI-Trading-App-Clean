from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from app.core.config import Settings
from app.services.allocation_engine import AllocationEngine
from app.services.redis_cache import RedisCache


@dataclass
class VirtualOrderManager:
    settings: Settings
    cache: RedisCache
    allocation_engine: AllocationEngine

    def stage_order(
        self,
        *,
        user_id: str,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str,
        limit_price: float | None,
        metadata: dict,
    ) -> dict:
        book_key = self._book_key(symbol, side, order_type, limit_price)
        book = self.cache.get_json(book_key) or self._empty_book(symbol, side, order_type, limit_price)
        intent_id = str(uuid4())
        intent = {
            "intent_id": intent_id,
            "user_id": user_id,
            "symbol": symbol,
            "side": side,
            "requested_quantity": quantity,
            "order_type": order_type,
            "limit_price": limit_price,
            **metadata,
        }
        book["intents"].append(intent)
        book["total_requested_quantity"] = round(
            sum(float(item["requested_quantity"]) for item in book["intents"]),
            self.settings.virtual_order_precision,
        )
        book["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.cache.set_json(book_key, book, ttl=self.settings.monitor_state_ttl_seconds)
        self.cache.set_json(
            self._aggregate_key(book["aggregate_id"]),
            {
                "aggregate_id": book["aggregate_id"],
                "symbol": symbol,
                "side": side,
                "order_type": order_type,
                "limit_price": limit_price,
                "intent_count": len(book["intents"]),
                "total_requested_quantity": book["total_requested_quantity"],
                "participant_user_ids": sorted({str(item.get("user_id", "")).strip() for item in book["intents"] if str(item.get("user_id", "")).strip()}),
                "status": "PENDING",
                "updated_at": book["updated_at"],
            },
            ttl=self.settings.monitor_state_ttl_seconds,
        )
        return {
            "aggregate_id": book["aggregate_id"],
            "book_key": book_key,
            "intent_id": intent_id,
            "intent_count": len(book["intents"]),
            "total_requested_quantity": book["total_requested_quantity"],
        }

    def flush_book(self, book_key: str, execute_callback) -> dict | None:
        book = self.load_book(book_key)
        if not book or not book.get("intents"):
            return None
        aggregate_id = book["aggregate_id"]
        try:
            order = execute_callback(
                symbol=book["symbol"],
                side=book["side"],
                quantity=float(book["total_requested_quantity"]),
                order_type=book["order_type"],
                limit_price=book.get("limit_price"),
                queue_context={
                    "aggregate_id": aggregate_id,
                    "virtual_child_count": len(book["intents"]),
                },
            )
        except Exception as exc:
            book["retry_count"] += 1
            book["last_error"] = str(exc)
            book["updated_at"] = datetime.now(timezone.utc).isoformat()
            self.cache.set_json(book_key, book, ttl=self.settings.monitor_state_ttl_seconds)
            self.cache.set_json(
                self._aggregate_key(aggregate_id),
                {
                    "aggregate_id": aggregate_id,
                    "symbol": book["symbol"],
                    "side": book["side"],
                    "participant_user_ids": sorted({str(item.get("user_id", "")).strip() for item in book["intents"] if str(item.get("user_id", "")).strip()}),
                    "status": "FAILED",
                    "retry_count": book["retry_count"],
                    "last_error": str(exc),
                    "updated_at": book["updated_at"],
                },
                ttl=self.settings.monitor_state_ttl_seconds,
            )
            raise
        return self.finalize_book(book_key, order)

    def load_book(self, book_key: str) -> dict | None:
        return self.cache.get_json(book_key)

    def finalize_book(self, book_key: str, order: dict) -> dict | None:
        book = self.load_book(book_key)
        if not book or not book.get("intents"):
            return None
        aggregate_id = book["aggregate_id"]
        executed_quantity = float(order.get("executedQty", 0.0))
        executed_price = float(order.get("fills", [{}])[0].get("price") or order.get("price") or 0.0)
        fee_paid = float(order.get("feePaid", 0.0))
        status = str(order.get("status", "UNKNOWN"))
        allocations = self.allocation_engine.allocate(
            intents=book["intents"],
            executed_quantity=executed_quantity,
            fee_paid=fee_paid,
            executed_price=executed_price,
            aggregate_order_id=str(order.get("orderId", aggregate_id)),
            aggregate_status=status,
        )
        remaining_intents = self._build_remaining_intents(book, allocations)
        aggregate_payload = {
            "aggregate_id": aggregate_id,
            "exchange_order_id": str(order.get("orderId", aggregate_id)),
            "symbol": book["symbol"],
            "side": book["side"],
            "status": status,
            "requested_quantity": float(book["total_requested_quantity"]),
            "executed_quantity": executed_quantity,
            "remaining_quantity": round(sum(item["requested_quantity"] for item in remaining_intents), self.settings.virtual_order_precision),
            "intent_count": len(book["intents"]),
            "allocation_count": len(allocations),
            "retry_count": book["retry_count"],
            "fee_paid": fee_paid,
            "executed_price": executed_price,
            "participant_user_ids": sorted({str(item.get("user_id", "")).strip() for item in book["intents"] if str(item.get("user_id", "")).strip()}),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if remaining_intents and book["retry_count"] < self.settings.virtual_order_max_retries:
            next_book = {
                **book,
                "intents": remaining_intents,
                "total_requested_quantity": aggregate_payload["remaining_quantity"],
                "retry_count": book["retry_count"] + 1,
                "updated_at": aggregate_payload["updated_at"],
                "last_error": None,
            }
            self.cache.set_json(book_key, next_book, ttl=self.settings.monitor_state_ttl_seconds)
            aggregate_payload["status"] = "PARTIALLY_FILLED"
        else:
            self.cache.delete(book_key)
        self.cache.set_json(
            self._aggregate_key(aggregate_id),
            aggregate_payload,
            ttl=self.settings.monitor_state_ttl_seconds,
        )
        return {
            "aggregate": aggregate_payload,
            "allocations": allocations,
            "book_key": book_key,
        }

    def flush_symbol(self, symbol: str, side: str, execute_callback) -> list[dict]:
        results: list[dict] = []
        for key in self.cache.keys(f"vom:book:{symbol}:{side}:*"):
            flushed = self.flush_book(key, execute_callback)
            if flushed is not None:
                results.append(flushed)
        return results

    def load_aggregate(self, aggregate_id: str) -> dict | None:
        return self.cache.get_json(self._aggregate_key(aggregate_id))

    def _empty_book(self, symbol: str, side: str, order_type: str, limit_price: float | None) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        return {
            "aggregate_id": str(uuid4()),
            "symbol": symbol,
            "side": side,
            "order_type": order_type,
            "limit_price": limit_price,
            "intents": [],
            "total_requested_quantity": 0.0,
            "retry_count": 0,
            "created_at": now,
            "updated_at": now,
            "last_error": None,
        }

    def _book_key(self, symbol: str, side: str, order_type: str, limit_price: float | None) -> str:
        limit_bucket = "market" if limit_price is None else f"{limit_price:.8f}"
        return f"vom:book:{symbol}:{side}:{order_type}:{limit_bucket}"

    def _aggregate_key(self, aggregate_id: str) -> str:
        return f"vom:aggregate:{aggregate_id}"

    def _build_remaining_intents(self, book: dict, allocations: list[dict]) -> list[dict]:
        remaining: list[dict] = []
        by_intent = {item["intent_id"]: item for item in allocations}
        for original in book["intents"]:
            allocated = by_intent.get(original["intent_id"])
            if allocated is None:
                continue
            if float(allocated["remaining_quantity"]) <= 0:
                continue
            remaining.append(
                {
                    **original,
                    "requested_quantity": float(allocated["remaining_quantity"]),
                }
            )
        return remaining

