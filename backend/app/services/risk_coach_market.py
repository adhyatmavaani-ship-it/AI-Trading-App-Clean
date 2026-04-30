from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
import json
import logging
import math
import time
import uuid

import httpx
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect
import websockets

from app.schemas.risk_coach import MarketCandlePayload, MarketStreamEnvelope


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class MarketClient:
    client_id: str
    websocket: WebSocket
    queue: asyncio.Queue[str]
    last_seen: float = field(default_factory=lambda: time.monotonic())
    sender_task: asyncio.Task[None] | None = None


class RiskCoachMarketService:
    def __init__(
        self,
        *,
        symbol: str = "BTCUSDT",
        interval: str = "1m",
        buffer_size: int = 200,
        per_client_queue_size: int = 64,
        ping_interval_seconds: float = 10.0,
        client_timeout_seconds: float = 20.0,
        send_timeout_seconds: float = 2.0,
    ) -> None:
        self.symbol = symbol.upper()
        self.interval = interval
        self.stream = f"{self.symbol.lower()}@kline_{self.interval}"
        self.buffer_size = buffer_size
        self.per_client_queue_size = per_client_queue_size
        self.ping_interval_seconds = ping_interval_seconds
        self.client_timeout_seconds = client_timeout_seconds
        self.send_timeout_seconds = send_timeout_seconds
        self._buffer: deque[MarketCandlePayload] = deque(maxlen=buffer_size)
        self._clients: dict[str, MarketClient] = {}
        self._broadcast_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=256)
        self._client_lock = asyncio.Lock()
        self._started = False
        self._shutdown = asyncio.Event()
        self._upstream_task: asyncio.Task[None] | None = None
        self._fanout_task: asyncio.Task[None] | None = None
        self._synthetic_task: asyncio.Task[None] | None = None
        self._source = "bootstrap"

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._shutdown.clear()
        await self._bootstrap_buffer()
        self._fanout_task = asyncio.create_task(self._fanout_loop(), name="risk-coach-fanout")
        self._upstream_task = asyncio.create_task(self._upstream_loop(), name="risk-coach-upstream")

    async def stop(self) -> None:
        self._shutdown.set()
        tasks = [task for task in (self._upstream_task, self._fanout_task, self._synthetic_task) if task is not None]
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("risk_coach_task_shutdown_failed")
        self._upstream_task = None
        self._fanout_task = None
        self._synthetic_task = None
        async with self._client_lock:
            clients = list(self._clients.values())
            self._clients.clear()
        for client in clients:
            if client.sender_task is not None:
                client.sender_task.cancel()
            try:
                await client.websocket.close(code=1001, reason="Server shutdown")
            except Exception:
                pass
        self._started = False

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        client = MarketClient(
            client_id=uuid.uuid4().hex,
            websocket=websocket,
            queue=asyncio.Queue(maxsize=self.per_client_queue_size),
        )
        client.sender_task = asyncio.create_task(self._client_sender(client), name=f"market-client-sender-{client.client_id}")
        async with self._client_lock:
            self._clients[client.client_id] = client
        await client.queue.put(json.dumps({"type": "hello", "stream": self.stream}))
        try:
            while not self._shutdown.is_set():
                try:
                    message = await asyncio.wait_for(websocket.receive_text(), timeout=self.ping_interval_seconds)
                    client.last_seen = time.monotonic()
                    if message.strip().lower() == "ping":
                        await client.queue.put(json.dumps({"type": "pong"}))
                    elif message.strip().lower() == "pong":
                        continue
                except TimeoutError:
                    if time.monotonic() - client.last_seen > self.client_timeout_seconds:
                        await websocket.close(code=1001, reason="Heartbeat timeout")
                        break
                    await client.queue.put(json.dumps({"type": "ping"}))
        except WebSocketDisconnect:
            pass
        finally:
            await self.disconnect(client.client_id)

    async def disconnect(self, client_id: str) -> None:
        async with self._client_lock:
            client = self._clients.pop(client_id, None)
        if client is None:
            return
        if client.sender_task is not None:
            client.sender_task.cancel()
            try:
                await client.sender_task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("risk_coach_client_sender_failed")

    def latest_candles(self, limit: int = 200) -> list[MarketCandlePayload]:
        items = list(self._buffer)
        if limit <= 0:
            return items
        return items[-limit:]

    def latest_close(self) -> float | None:
        return self._buffer[-1].c if self._buffer else None

    def snapshot_prices_since(self, timestamp_seconds: int) -> list[float]:
        prices: list[float] = []
        threshold_ms = int(timestamp_seconds * 1000)
        for candle in self._buffer:
            if candle.t >= threshold_ms:
                prices.extend([candle.o, candle.h, candle.l, candle.c])
        return prices

    def source(self) -> str:
        return self._source

    async def _bootstrap_buffer(self) -> None:
        url = "https://api.binance.com/api/v3/klines"
        params = {"symbol": self.symbol, "interval": self.interval, "limit": self.buffer_size}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                rows = response.json()
            self._buffer.clear()
            for row in rows:
                self._buffer.append(
                    MarketCandlePayload(
                        t=int(row[0]),
                        o=float(row[1]),
                        h=float(row[2]),
                        l=float(row[3]),
                        c=float(row[4]),
                        v=float(row[5]),
                    )
                )
            self._source = "binance_rest"
        except Exception:
            logger.warning("risk_coach_bootstrap_fallback", exc_info=True)
            self._source = "synthetic"
            self._seed_synthetic_buffer()

    def _seed_synthetic_buffer(self) -> None:
        self._buffer.clear()
        base = 68000.0
        now_ms = int(time.time() * 1000)
        step_ms = 60_000
        for index in range(self.buffer_size):
            drift = math.sin(index / 9) * 55.0
            close = base + drift + (index * 2.0)
            open_price = close - math.sin(index / 4) * 18.0
            high = max(open_price, close) + 22.0
            low = min(open_price, close) - 19.0
            self._buffer.append(
                MarketCandlePayload(
                    t=now_ms - ((self.buffer_size - index) * step_ms),
                    o=round(open_price, 2),
                    h=round(high, 2),
                    l=round(low, 2),
                    c=round(close, 2),
                    v=1500.0 + (index % 20) * 17.0,
                )
            )

    async def _upstream_loop(self) -> None:
        url = f"wss://stream.binance.com:9443/ws/{self.stream}"
        backoff_seconds = 1.0
        while not self._shutdown.is_set():
            try:
                async with websockets.connect(url, ping_interval=None, close_timeout=2.0) as socket:
                    self._source = "binance_ws"
                    backoff_seconds = 1.0
                    async for raw in socket:
                        payload = json.loads(raw)
                        kline = payload.get("k") or {}
                        envelope = MarketStreamEnvelope(
                            stream=self.stream,
                            data=MarketCandlePayload(
                                t=int(kline.get("t", 0)),
                                o=float(kline.get("o", 0.0)),
                                h=float(kline.get("h", 0.0)),
                                l=float(kline.get("l", 0.0)),
                                c=float(kline.get("c", 0.0)),
                                v=float(kline.get("v", 0.0)),
                            ),
                        )
                        self._apply_delta(envelope.data)
                        await self._queue_broadcast(envelope.model_dump_json())
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning("risk_coach_upstream_reconnect", exc_info=True)
                self._source = "synthetic"
                if self._synthetic_task is None or self._synthetic_task.done():
                    self._synthetic_task = asyncio.create_task(self._synthetic_loop(), name="risk-coach-synthetic")
                await asyncio.sleep(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 2.0, 20.0)

    async def _synthetic_loop(self) -> None:
        while self._source == "synthetic" and not self._shutdown.is_set():
            last = self._buffer[-1] if self._buffer else MarketCandlePayload(t=int(time.time() * 1000), o=68000, h=68010, l=67990, c=68005, v=1000)
            tick = int(time.time() * 1000)
            shift = math.sin(tick / 120000.0) * 14.0
            close = max(1.0, last.c + shift)
            candle = MarketCandlePayload(
                t=tick - (tick % 60_000),
                o=last.c,
                h=max(last.c, close) + 6.0,
                l=min(last.c, close) - 6.0,
                c=close,
                v=last.v + 8.0,
            )
            self._apply_delta(candle)
            await self._queue_broadcast(MarketStreamEnvelope(stream=self.stream, data=candle).model_dump_json())
            await asyncio.sleep(1.0)

    def _apply_delta(self, candle: MarketCandlePayload) -> None:
        if self._buffer and self._buffer[-1].t == candle.t:
            self._buffer[-1] = candle
            return
        self._buffer.append(candle)

    async def _queue_broadcast(self, message: str) -> None:
        if self._broadcast_queue.full():
            try:
                self._broadcast_queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        await self._broadcast_queue.put(message)

    async def _fanout_loop(self) -> None:
        while not self._shutdown.is_set():
            message = await self._broadcast_queue.get()
            async with self._client_lock:
                clients = list(self._clients.values())
            stale_ids: list[str] = []
            for client in clients:
                if client.queue.full():
                    try:
                        client.queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                try:
                    client.queue.put_nowait(message)
                except asyncio.QueueFull:
                    stale_ids.append(client.client_id)
            for client_id in stale_ids:
                await self.disconnect(client_id)

    async def _client_sender(self, client: MarketClient) -> None:
        while not self._shutdown.is_set():
            message = await client.queue.get()
            try:
                await asyncio.wait_for(client.websocket.send_text(message), timeout=self.send_timeout_seconds)
            except (TimeoutError, WebSocketDisconnect, RuntimeError):
                break
            except Exception:
                logger.warning("risk_coach_client_send_failed", exc_info=True)
                break

