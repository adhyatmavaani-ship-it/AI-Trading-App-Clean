from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.services.redis_cache import RedisCache


@dataclass
class RedisStateManager:
    settings: Settings
    cache: RedisCache

    def _active_trade_index_key(self) -> str:
        return "active_trade:index"

    def save_active_trade(self, trade_id: str, payload: dict) -> None:
        self.cache.set_json(
            f"active_trade:{trade_id}",
            payload,
            ttl=self.settings.monitor_state_ttl_seconds,
        )
        self._remember_active_trade_id(trade_id)

    def load_active_trade(self, trade_id: str) -> dict | None:
        return self.cache.get_json(f"active_trade:{trade_id}")

    def clear_active_trade(self, trade_id: str) -> None:
        self.cache.delete(f"active_trade:{trade_id}")
        self._forget_active_trade_id(trade_id)

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
        seen_trade_ids: set[str] = set()
        indexed_ids = self._active_trade_ids()
        for trade_id in indexed_ids:
            trade = self.load_active_trade(trade_id)
            if not trade:
                continue
            normalized_trade_id = str(trade.get("trade_id", trade_id) or trade_id)
            if normalized_trade_id in seen_trade_ids:
                continue
            seen_trade_ids.add(normalized_trade_id)
            trades.append(trade)
        if not hasattr(self.cache, "keys"):
            return trades
        for key in self.cache.keys("active_trade:*"):
            trade = self.cache.get_json(key)
            if not trade:
                continue
            normalized_trade_id = str(trade.get("trade_id", "") or "")
            if normalized_trade_id and normalized_trade_id in seen_trade_ids:
                continue
            if normalized_trade_id:
                seen_trade_ids.add(normalized_trade_id)
            trades.append(trade)
        return trades

    def restore_orders(self) -> list[dict]:
        orders: list[dict] = []
        for key in self.cache.keys("order:*"):
            order = self.cache.get_json(key)
            if order:
                orders.append(order)
        return orders

    def register_monitored_trade(self, trade_id: str, payload: dict | None = None) -> None:
        self.cache.set_json(
            f"monitor:trade:{trade_id}",
            payload or {"trade_id": trade_id},
            ttl=self.settings.monitor_state_ttl_seconds,
        )

    def unregister_monitored_trade(self, trade_id: str) -> None:
        self.cache.delete(f"monitor:trade:{trade_id}")

    def restore_monitored_trades(self) -> list[dict]:
        trades: list[dict] = []
        for key in self.cache.keys("monitor:trade:*"):
            trade = self.cache.get_json(key)
            if trade:
                trades.append(trade)
        return trades

    def _active_trade_ids(self) -> list[str]:
        payload = self.cache.get_json(self._active_trade_index_key()) or {}
        ids = payload.get("trade_ids") or []
        return [str(item) for item in ids if str(item).strip()]

    def _remember_active_trade_id(self, trade_id: str) -> None:
        existing = self._active_trade_ids()
        if trade_id not in existing:
            existing.append(trade_id)
        self.cache.set_json(
            self._active_trade_index_key(),
            {"trade_ids": existing},
            ttl=self.settings.monitor_state_ttl_seconds,
        )

    def _forget_active_trade_id(self, trade_id: str) -> None:
        remaining = [item for item in self._active_trade_ids() if item != trade_id]
        self.cache.set_json(
            self._active_trade_index_key(),
            {"trade_ids": remaining},
            ttl=self.settings.monitor_state_ttl_seconds,
        )
