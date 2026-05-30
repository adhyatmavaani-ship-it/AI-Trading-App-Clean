from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from app.services.advanced_trading_state import AdvancedTradingStateRepository
from app.services.strategy_performance_analytics import StrategyPerformanceAnalyticsProcessor
from app.services.websocket_manager import TradingUpdateWebSocketManager, get_trading_update_websocket_manager


@dataclass(frozen=True)
class MockOrderBookDecision:
    action_type: str
    accepted: bool
    reason: str
    venue: str


class MockTestnetOrderBook:
    """Secure mock/testnet sink for chart events.

    It records intended order-book state transitions for UI validation. It does
    not submit broker orders, place live trades, or bypass existing risk gates.
    """

    def decide(self, order: dict[str, Any], *, mode: str, credential: dict[str, Any] | None) -> MockOrderBookDecision:
        status = str(order.get("status") or "").upper()
        if status not in {"STAGED", "ACTIVE"}:
            return MockOrderBookDecision(
                action_type="IGNORE_NON_EXECUTABLE_CHART_STATE",
                accepted=True,
                reason=f"chart order status {status or 'UNKNOWN'} is advisory",
                venue=mode,
            )
        if mode == "testnet" and credential is None:
            return MockOrderBookDecision(
                action_type="REJECT_TESTNET_CREDENTIAL_MISSING",
                accepted=False,
                reason="testnet mode requires an encrypted user API key",
                venue=mode,
            )
        if not any(order.get(field) for field in ("limit_price", "stop_loss", "take_profit")):
            return MockOrderBookDecision(
                action_type="REJECT_PRICE_LEVEL_MISSING",
                accepted=False,
                reason="chart order has no executable price level",
                venue=mode,
            )
        return MockOrderBookDecision(
            action_type="SYNC_MOCK_TESTNET_ORDER",
            accepted=True,
            reason="chart line mapped to mock/testnet order-book state",
            venue=mode,
        )


class ChartExecutionBridgeWorker:
    """Consumes chart sync events into mock/testnet order-book records only."""

    def __init__(
        self,
        *,
        repository: AdvancedTradingStateRepository,
        order_book: MockTestnetOrderBook | None = None,
        analytics_processor: StrategyPerformanceAnalyticsProcessor | None = None,
        websocket_manager: TradingUpdateWebSocketManager | None = None,
        mode: str = "mock",
        interval_seconds: float = 1.0,
        batch_size: int = 25,
    ) -> None:
        self._repository = repository
        self._order_book = order_book or MockTestnetOrderBook()
        self._analytics_processor = analytics_processor or StrategyPerformanceAnalyticsProcessor()
        self._websocket_manager = websocket_manager or get_trading_update_websocket_manager()
        self._mode = "testnet" if str(mode).lower() == "testnet" else "mock"
        self._interval_seconds = max(float(interval_seconds), 0.1)
        self._batch_size = max(1, min(int(batch_size), 100))
        self._task: asyncio.Task | None = None
        self._stopped = asyncio.Event()

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stopped.clear()
        self._task = asyncio.create_task(self.run_forever(), name="chart-execution-bridge")

    async def stop(self) -> None:
        self._stopped.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def run_once(self) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        events = self._repository.claim_pending_chart_order_events(limit=self._batch_size)
        for event in events:
            try:
                order = dict(event.get("payload") or {})
                credential = self._repository.latest_user_api_key_metadata(user_id=str(order.get("user_id") or event["user_id"]))
                decision = self._order_book.decide(order, mode=self._mode, credential=credential)
                action = self._repository.record_chart_order_testnet_action(
                    event_id=event["event_id"],
                    order=order,
                    mode=self._mode,
                    credential=credential,
                    action_payload={
                        "action_type": decision.action_type,
                        "accepted": decision.accepted,
                        "reason": decision.reason,
                        "venue": decision.venue,
                        "ai_strategy_id": order.get("ai_strategy_id"),
                        "workspace_mode": order.get("workspace_mode"),
                        "advisory_bridge": True,
                        "live_broker_submission": False,
                    },
                )
                self._repository.complete_chart_order_event(
                    event_id=event["event_id"],
                    error=None if decision.accepted else decision.reason,
                )
                await self._websocket_manager.broadcast_chart_order_action(
                    user_id=order["user_id"],
                    action=action,
                )
                await self._broadcast_strategy_performance(order["user_id"])
                actions.append(action)
            except Exception as exc:
                self._repository.complete_chart_order_event(event_id=event["event_id"], error=str(exc)[:300])
        return actions

    async def _broadcast_strategy_performance(self, user_id: str) -> None:
        actions = self._repository.list_chart_order_testnet_actions(user_id=user_id, limit=120)
        snapshot = self._analytics_processor.snapshot(user_id=user_id, actions=actions)
        await self._websocket_manager.broadcast_strategy_performance_update(
            user_id=user_id,
            snapshot=snapshot,
        )

    async def run_forever(self) -> None:
        while not self._stopped.is_set():
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                # Bridge failures are intentionally isolated from trading startup.
                pass
            await asyncio.sleep(self._interval_seconds)
