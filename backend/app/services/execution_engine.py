from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, ROUND_UP
import logging
import random
import time

from binance.client import Client
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import Settings
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
        self.client = None
        if self.settings.trading_mode == "paper":
            return
        secret_manager = SecretManagerService(self.settings.secret_manager_project_id)
        api_key = self.settings.binance_api_key or secret_manager.access_secret("binance-api-key")
        api_secret = self.settings.binance_api_secret or secret_manager.access_secret("binance-api-secret")
        self.client = Client(api_key, api_secret)
        if self.settings.binance_testnet:
            self.client.API_URL = "https://testnet.binance.vision/api"

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
        if self.client is None:
            raise RuntimeError("Live execution is unavailable while TRADING_MODE is not live")
        self._throttle_exchange("binance:place_order")
        scheduled_delay_ms = int((queue_context or {}).get("scheduled_delay_ms", 0))
        if scheduled_delay_ms > 0:
            time.sleep(scheduled_delay_ms / 1000)
        route = self.router.route(symbol, side, quantity)
        if route["broadcast_delay_ms"]:
            time.sleep(route["broadcast_delay_ms"] / 1000)
        started = time.perf_counter()
        ticker = self.client.get_symbol_ticker(symbol=symbol)
        self.latency_monitor.record_sync("binance_ticker", (time.perf_counter() - started) * 1000)
        market_price = float(ticker["price"])
        normalized_quantity, normalized_limit_price = self._normalize_order_request(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
            reference_price=market_price,
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
                )
        if order_type == "LIMIT" and normalized_limit_price is not None:
            if abs(normalized_limit_price - market_price) > allowed_slippage:
                raise ValueError("Requested limit price exceeds slippage guardrail")
            self._throttle_exchange("binance:create_limit_order")
            order = self.client.create_order(
                symbol=symbol,
                side=side,
                type=Client.ORDER_TYPE_LIMIT,
                timeInForce=Client.TIME_IN_FORCE_GTC,
                quantity=f"{normalized_quantity:.8f}",
                price=f"{normalized_limit_price:.8f}",
            )
            if order.get("status") in {"NEW", "PARTIALLY_FILLED"}:
                order = self.reconcile_order(symbol, int(order["orderId"]), side, normalized_quantity, market_price)
            return order
        self._throttle_exchange("binance:create_market_order")
        return self.client.create_order(
            symbol=symbol,
            side=side,
            type=Client.ORDER_TYPE_MARKET,
            quantity=f"{normalized_quantity:.8f}",
        )

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
    ) -> dict:
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
            )
            self._throttle_exchange("binance:chunk_order")
            order = self.client.create_order(
                symbol=symbol,
                side=side,
                type=Client.ORDER_TYPE_MARKET,
                quantity=f"{chunk_qty:.8f}",
            )
            orders.append(order)
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
        self.latency_monitor.record_sync("binance_chunked_execution", latency_ms)
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
        }

    def fetch_order_status(self, symbol: str, order_id: int) -> dict:
        if self.client is None:
            raise RuntimeError("Live execution client not initialized")
        self._throttle_exchange("binance:order_status")
        started = time.perf_counter()
        status = self.client.get_order(symbol=symbol, orderId=order_id)
        self.latency_monitor.record_sync("binance_order_status", (time.perf_counter() - started) * 1000)
        return status

    def reconcile_order(
        self, symbol: str, order_id: int, side: str, quantity: float, market_price: float
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
            self._throttle_exchange("binance:fallback_market_order")
            fallback = self.client.create_order(
                symbol=symbol,
                side=side,
                type=Client.ORDER_TYPE_MARKET,
                quantity=remaining_qty,
            )
            fallback["filledRatio"] = 1.0
            fallback["slippageBps"] = self.settings.slippage_bps
            fallback["feePaid"] = float(fallback.get("cummulativeQuoteQty", 0.0)) * (
                self.settings.taker_fee_bps / 10_000
            )
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
    ) -> tuple[float, float | None]:
        rules = self._symbol_rules(symbol)
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

    def _symbol_rules(self, symbol: str) -> dict[str, float]:
        cache_key = f"binance:symbol_rules:{symbol.upper()}"
        cached = self.cache.get_json(cache_key)
        if cached is not None:
            return {key: float(value) for key, value in cached.items()}
        if self.client is None:
            return {
                "min_qty": 0.0,
                "max_qty": float("inf"),
                "step_size": 0.00000001,
                "tick_size": 0.00000001,
                "min_notional": self.settings.exchange_min_notional,
            }
        info = self.client.get_symbol_info(symbol.upper()) or {}
        filters = {item.get("filterType"): item for item in info.get("filters", [])}
        lot_size = filters.get("LOT_SIZE", {})
        price_filter = filters.get("PRICE_FILTER", {})
        min_notional_filter = filters.get("MIN_NOTIONAL") or filters.get("NOTIONAL") or {}
        rules = {
            "min_qty": float(lot_size.get("minQty", 0.0) or 0.0),
            "max_qty": float(lot_size.get("maxQty", 0.0) or 0.0) or float("inf"),
            "step_size": float(lot_size.get("stepSize", 0.00000001) or 0.00000001),
            "tick_size": float(price_filter.get("tickSize", 0.00000001) or 0.00000001),
            "min_notional": float(min_notional_filter.get("minNotional", self.settings.exchange_min_notional) or self.settings.exchange_min_notional),
        }
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
