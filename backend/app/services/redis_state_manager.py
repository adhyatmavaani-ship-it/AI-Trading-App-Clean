from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.services.redis_cache import RedisCache


@dataclass
class RedisStateManager:
    settings: Settings
    cache: RedisCache

    def save_active_trade(self, trade_id: str, payload: dict) -> None:
        self.cache.set_json(
            f"active_trade:{trade_id}",
            payload,
            ttl=self.settings.monitor_state_ttl_seconds,
        )

    def load_active_trade(self, trade_id: str) -> dict | None:
        return self.cache.get_json(f"active_trade:{trade_id}")

    def clear_active_trade(self, trade_id: str) -> None:
        self.cache.delete(f"active_trade:{trade_id}")

    def remember_order(self, order_id: str, payload: dict) -> None:
        self.cache.set_json(
            f"order:{order_id}",
            payload,
            ttl=self.settings.monitor_state_ttl_seconds,
        )

    def load_order(self, order_id: str) -> dict | None:
        return self.cache.get_json(f"order:{order_id}")

    def remember_signal_trade(self, signal_id: str, trade_id: str) -> None:
        if not signal_id:
            return
        self.cache.set_json(
            f"signal_trade:{signal_id}",
            {"trade_id": trade_id},
            ttl=self.settings.signal_dedup_ttl_seconds,
        )

    def load_signal_trade(self, signal_id: str) -> str | None:
        payload = self.cache.get_json(f"signal_trade:{signal_id}")
        if not payload:
            return None
        trade_id = str(payload.get("trade_id", "") or "").strip()
        return trade_id or None

    def restore_active_trades(self) -> list[dict]:
        trades: list[dict] = []
        for key in self.cache.keys("active_trade:*"):
            trade = self.cache.get_json(key)
            if trade:
                trades.append(trade)
        return trades

    def restore_orders(self) -> list[dict]:
        orders: list[dict] = []
        for key in self.cache.keys("order:*"):
            order = self.cache.get_json(key)
            if order:
                orders.append(order)
        return orders
