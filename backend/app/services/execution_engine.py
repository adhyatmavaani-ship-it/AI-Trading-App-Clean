from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, ROUND_UP
import logging
import random
import time
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import Settings
from app.services.exchange_adapters import CcxtExchangeAdapter, ExchangeAdapter
from app.services.latency_monitor import LatencyMonitor
from app.services.liquidity_slippage import LiquiditySlippageEngine
from app.services.multi_chain_router import MultiChainRouter
from app.services.execution_queue_manager import ExecutionQueueManager
from app.services.redis_cache import RedisCache
from app.services.secret_manager import SecretManagerService
from app.services.shard_manager import ShardManager

logger = logging.getLogger(__name__)


@dataclass
class ExecutionEngine:
    settings: Settings

    def __post_init__(self) -> None:
        self.cache = RedisCache(self.settings.redis_url)
        self.latency_monitor = LatencyMonitor(self.settings, self.cache)
        self.shard_manager = ShardManager(self.settings)
        self.queue_manager = ExecutionQueueManager(self.settings, self.cache, self.shard_manager)
        self.slippage_engine = LiquiditySlippageEngine(
            slippage_threshold_bps=float(self.settings.max_slippage_bps),
            chunk_delay_ms=self.settings.execution_chunk_delay_ms,
        )
        self.router = MultiChainRouter(self.settings)
        self.exchange_clients: dict[str, ExchangeAdapter] = {}
        if self.settings.trading_mode == "paper":
            return
        self._hydrate_exchange_secrets()
        for exchange_id in self._configured_exchanges():
            try:
                self.exchange_clients[exchange_id] = CcxtExchangeAdapter(self.settings, exchange_id)
            except Exception as exc:
                logger.warning(
                    "exchange_adapter_init_failed",
                    extra={"event": "exchange_adapter_init_failed", "context": {"exchange": exchange_id, "error": str(exc)[:200]}},
                )
        if not self.exchange_clients:
            raise RuntimeError("No live exchange adapters could be initialized")

    @retry(wait=wait_exponential(min=1, max=8), stop=stop_after_attempt(3), reraise=True)
    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str,
        limit_price: float | None = None,
        order_book: dict | None = None,
        queue_context: dict | None = None,
    ) -> dict:
        if not self.exchange_clients:
            raise RuntimeError("Live execution is unavailable while TRADING_MODE is not live")
        scheduled_delay_ms = int((queue_context or {}).get("scheduled_delay_ms", 0))
        if scheduled_delay_ms > 0:
            time.sleep(scheduled_delay_ms / 1000)
        route = self.router.route(symbol, side, quantity)
        if route["broadcast_delay_ms"]:
            time.sleep(route["broadcast_delay_ms"] / 1000)
        last_error: Exception | None = None
        for exchange_id, exchange_client in self.exchange_clients.items():
            try:
                self._throttle_exchange(f"{exchange_id}:place_order")
                started = time.perf_counter()
                market_price = exchange_client.fetch_ticker_price(symbol)
                self.latency_monitor.record_sync(f"{exchange_id}_ticker", (time.perf_counter() - started) * 1000)
                normalized_quantity, normalized_limit_price = self._normalize_order_request(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    order_type=order_type,
                    limit_price=limit_price,
                    reference_price=market_price,
                    exchange_id=exchange_id,
                )
                allowed_slippage = market_price * (self.settings.slippage_bps / 10_000)
                if order_book:
                    plan = self.slippage_engine.estimate(order_book, side, normalized_quantity)
                    if plan["chunks"] > 1:
                        return self.execute_chunked_order(
                            symbol=symbol,
                            side=side,
                            quantity=normalized_quantity,
                            order_type=order_type,
                            market_price=market_price,
                            plan=plan,
                            queue_context=queue_context,
                            exchange_id=exchange_id,
                        )
                if order_type == "LIMIT" and normalized_limit_price is not None:
                    if abs(normalized_limit_price - market_price) > allowed_slippage:
                        raise ValueError("Requested limit price exceeds slippage guardrail")
                    self._throttle_exchange(f"{exchange_id}:create_limit_order")
                    order = exchange_client.create_order(
                        symbol=symbol,
                        side=side,
                        order_type="LIMIT",
                        quantity=normalized_quantity,
                        limit_price=normalized_limit_price,
                    )
                    self._remember_order_exchange(order.get("orderId"), exchange_id)
                    if order.get("status") in {"NEW", "PARTIALLY_FILLED"}:
                        order = self.reconcile_order(symbol, str(order["orderId"]), side, normalized_quantity, market_price)
                    return order
                self._throttle_exchange(f"{exchange_id}:create_market_order")
                order = exchange_client.create_order(
                    symbol=symbol,
                    side=side,
                    order_type="MARKET",
                    quantity=normalized_quantity,
                )
                self._remember_order_exchange(order.get("orderId"), exchange_id)
                return order
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "exchange_order_failed",
                    extra={"event": "exchange_order_failed", "context": {"exchange": exchange_id, "symbol": symbol, "error": str(exc)[:200]}},
                )
        if last_error is not None:
            raise last_error
        raise RuntimeError("No exchange clients available for execution")

    def place_virtual_order(
        self,
        symbol: str,
        side: str,
        intents: list[dict],
        order_type: str,
        limit_price: float | None = None,
        order_book: dict | None = None,
        queue_context: dict | None = None,
    ) -> dict:
        aggregate_quantity = sum(float(intent.get("requested_quantity", 0.0)) for intent in intents)
        if aggregate_quantity <= 0:
            raise ValueError("Virtual order batch has no executable quantity")
        order = self.place_order(
            symbol=symbol,
            side=side,
            quantity=aggregate_quantity,
            order_type=order_type,
            limit_price=limit_price,
            order_book=order_book,
            queue_context={
                **(queue_context or {}),
                "virtual_child_count": len(intents),
                "aggregate_quantity": aggregate_quantity,
            },
        )
        order["aggregateRequestedQty"] = aggregate_quantity
        order["childOrderCount"] = len(intents)
        order["virtualOrder"] = True
        return order

    def execute_chunked_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str,
        market_price: float,
        plan: dict,
        queue_context: dict | None = None,
        exchange_id: str | None = None,
    ) -> dict:
        exchange_key = exchange_id or self.settings.primary_exchange
        exchange_client = self.exchange_clients[exchange_key]
        orders = []
        started = time.perf_counter()
        chunk_delays_ms: list[int] = []
        for chunk_idx in range(plan["chunks"]):
            chunk_qty = plan["chunk_quantity"] if chunk_idx < plan["chunks"] - 1 else quantity - plan["chunk_quantity"] * (plan["chunks"] - 1)
            chunk_qty, _ = self._normalize_order_request(
                symbol=symbol,
                side=side,
                quantity=chunk_qty,
                order_type=order_type,
                limit_price=None,
                reference_price=market_price,
                exchange_id=exchange_key,
            )
            self._throttle_exchange(f"{exchange_key}:chunk_order")
            order = exchange_client.create_order(
                symbol=symbol,
                side=side,
                order_type="MARKET",
                quantity=chunk_qty,
            )
            orders.append(order)
            self._remember_order_exchange(order.get("orderId"), exchange_key)
            if chunk_idx < plan["chunks"] - 1:
                delay_seconds = random.randint(
                        self.settings.chunk_delay_min_seconds,
                        self.settings.chunk_delay_max_seconds,
                    )
                chunk_delays_ms.append(delay_seconds * 1000)
                logger.info(
                    "chunk_delay_selected",
                    extra={
                        "event": "chunk_delay_selected",
                        "context": {
                            "symbol": symbol,
                            "chunk_idx": chunk_idx,
                            "delay_seconds": delay_seconds,
                            "scheduled_delay_ms": int((queue_context or {}).get("scheduled_delay_ms", 0)),
                        },
                    },
                )
                time.sleep(delay_seconds)
        executed_qty = sum(float(order.get("executedQty", chunk_qty)) for order, chunk_qty in zip(orders, [plan["chunk_quantity"]] * len(orders)))
        cumulative_quote = sum(float(order.get("cummulativeQuoteQty", 0.0)) for order in orders)
        avg_price = cumulative_quote / max(executed_qty, 1e-8) if cumulative_quote else market_price
        latency_ms = (time.perf_counter() - started) * 1000
        self.latency_monitor.record_sync(f"{exchange_key}_chunked_execution", latency_ms)
        return {
            "orderId": orders[-1]["orderId"],
            "status": "FILLED",
            "executedQty": f"{executed_qty:.8f}",
            "price": f"{avg_price:.8f}",
            "fills": [{"price": f"{avg_price:.8f}", "qty": f"{executed_qty:.8f}"}],
            "filledRatio": 1.0,
            "slippageBps": abs(avg_price - market_price) / max(market_price, 1e-8) * 10_000,
            "feePaid": cumulative_quote * (self.settings.taker_fee_bps / 10_000),
            "executionLatencyMs": latency_ms,
            "chunkCount": plan["chunks"],
            "chunkDelaysMs": chunk_delays_ms,
            "exchange": exchange_key,
        }

    def fetch_order_status(self, symbol: str, order_id: str | int) -> dict:
        if not self.exchange_clients:
            raise RuntimeError("Live execution client not initialized")
        exchange_id = self._order_exchange(order_id) or self.settings.primary_exchange
        exchange_client = self.exchange_clients.get(exchange_id)
        if exchange_client is None:
            raise RuntimeError(f"Exchange client '{exchange_id}' is not initialized")
        self._throttle_exchange(f"{exchange_id}:order_status")
        started = time.perf_counter()
        status = exchange_client.fetch_order(symbol=symbol, order_id=str(order_id))
        self.latency_monitor.record_sync(f"{exchange_id}_order_status", (time.perf_counter() - started) * 1000)
        return status

    def reconcile_order(
        self, symbol: str, order_id: str | int, side: str, quantity: float, market_price: float
    ) -> dict:
        status = self.fetch_order_status(symbol, order_id)
        executed_qty = float(status.get("executedQty", 0))
        original_qty = float(status.get("origQty", quantity))
        if status.get("status") == "FILLED":
            status["filledRatio"] = min(1.0, executed_qty / max(original_qty, 1e-8))
            status["slippageBps"] = abs(float(status.get("price", market_price)) - market_price) / market_price * 10_000
            status["feePaid"] = float(status.get("cummulativeQuoteQty", 0.0)) * (self.settings.taker_fee_bps / 10_000)
            return status
        remaining_qty = max(0.0, original_qty - executed_qty)
        logger.warning(
            "limit_order_fallback",
            extra={"event": "limit_order_fallback", "context": {"symbol": symbol, "order_id": order_id}},
        )
        if remaining_qty > 0:
            exchange_id = self._order_exchange(order_id) or self.settings.primary_exchange
            exchange_client = self.exchange_clients[exchange_id]
            self._throttle_exchange(f"{exchange_id}:fallback_market_order")
            fallback = exchange_client.create_order(
                symbol=symbol,
                side=side,
                order_type="MARKET",
                quantity=remaining_qty,
            )
            fallback["filledRatio"] = 1.0
            fallback["slippageBps"] = self.settings.slippage_bps
            fallback["feePaid"] = float(fallback.get("cummulativeQuoteQty", 0.0)) * (
                self.settings.taker_fee_bps / 10_000
            )
            self._remember_order_exchange(fallback.get("orderId"), exchange_id)
            return fallback
        status["filledRatio"] = min(1.0, executed_qty / max(original_qty, 1e-8))
        status["slippageBps"] = 0.0
        status["feePaid"] = float(status.get("cummulativeQuoteQty", 0.0)) * (self.settings.maker_fee_bps / 10_000)
        return status

    def _throttle_exchange(self, scope: str) -> None:
        backoff_seconds = self.queue_manager.throttle(scope)
        if backoff_seconds <= 0:
            return
        logger.warning(
            "exchange_throttled",
            extra={"event": "exchange_throttled", "context": {"scope": scope, "backoff_seconds": backoff_seconds}},
        )
        time.sleep(backoff_seconds)

    def _normalize_order_request(
        self,
        *,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str,
        limit_price: float | None,
        reference_price: float,
        exchange_id: str,
    ) -> tuple[float, float | None]:
        rules = self._symbol_rules(symbol, exchange_id=exchange_id)
        normalized_quantity = self._normalize_quantity(
            quantity=quantity,
            step_size=rules["step_size"],
            min_qty=rules["min_qty"],
            max_qty=rules["max_qty"],
        )
        normalized_limit_price = limit_price
        if order_type == "LIMIT":
            if limit_price is None:
                raise ValueError("limit_price is required for LIMIT orders")
            normalized_limit_price = self._normalize_price(
                price=limit_price,
                tick_size=rules["tick_size"],
                side=side,
            )
        reference_notional_price = normalized_limit_price if normalized_limit_price is not None else reference_price
        if normalized_quantity * reference_notional_price < rules["min_notional"]:
            raise ValueError("Order does not satisfy exchange minimum notional")
        return normalized_quantity, normalized_limit_price

    def _symbol_rules(self, symbol: str, *, exchange_id: str) -> dict[str, float]:
        cache_key = f"{exchange_id}:symbol_rules:{symbol.upper()}"
        cached = self.cache.get_json(cache_key)
        if cached is not None:
            return {key: float(value) for key, value in cached.items()}
        exchange_client = self.exchange_clients.get(exchange_id)
        if exchange_client is None:
            return {
                "min_qty": 0.0,
                "max_qty": float("inf"),
                "step_size": 0.00000001,
                "tick_size": 0.00000001,
                "min_notional": self.settings.exchange_min_notional,
            }
        rules = exchange_client.fetch_symbol_rules(symbol)
        serializable_rules = {
            key: value
            for key, value in rules.items()
            if value != float("inf")
        }
        self.cache.set_json(cache_key, serializable_rules, ttl=self.settings.monitor_state_ttl_seconds)
        return rules

    def _normalize_quantity(
        self,
        *,
        quantity: float,
        step_size: float,
        min_qty: float,
        max_qty: float,
    ) -> float:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        normalized = self._round_to_step(quantity, step_size, rounding=ROUND_DOWN)
        if normalized < min_qty:
            raise ValueError("Order quantity falls below exchange minimum quantity")
        if normalized > max_qty:
            normalized = self._round_to_step(max_qty, step_size, rounding=ROUND_DOWN)
        if normalized <= 0:
            raise ValueError("Order quantity is not executable after exchange normalization")
        return float(normalized)

    def _normalize_price(self, *, price: float, tick_size: float, side: str) -> float:
        if price <= 0:
            raise ValueError("limit_price must be positive")
        rounding = ROUND_DOWN if side.upper() == "BUY" else ROUND_UP
        normalized = self._round_to_step(price, tick_size, rounding=rounding)
        if normalized <= 0:
            raise ValueError("limit_price is not executable after exchange normalization")
        return float(normalized)

    def _round_to_step(self, value: float, step: float, *, rounding: str) -> Decimal:
        decimal_value = Decimal(str(value))
        decimal_step = Decimal(str(step))
        if decimal_step <= 0:
            return decimal_value
        return decimal_value.quantize(decimal_step, rounding=rounding)

    def _configured_exchanges(self) -> list[str]:
        ordered = [self.settings.primary_exchange, *self.settings.backup_exchanges]
        unique: list[str] = []
        for exchange_id in ordered:
            normalized = str(exchange_id).strip().lower()
            if normalized and normalized not in unique:
                unique.append(normalized)
        return unique

    def _hydrate_exchange_secrets(self) -> None:
        secret_manager = SecretManagerService(self.settings.secret_manager_project_id)
        if not self.settings.binance_api_key:
            self.settings.binance_api_key = secret_manager.access_secret("binance-api-key")
        if not self.settings.binance_api_secret:
            self.settings.binance_api_secret = secret_manager.access_secret("binance-api-secret")

    def _remember_order_exchange(self, order_id: str | None, exchange_id: str) -> None:
        if not order_id:
            return
        self.cache.set(f"order:exchange:{order_id}", exchange_id, ttl=self.settings.monitor_state_ttl_seconds)

    def _order_exchange(self, order_id: str | int) -> str | None:
        value = self.cache.get(f"order:exchange:{order_id}")
        if not value:
            return None
        return str(value)
