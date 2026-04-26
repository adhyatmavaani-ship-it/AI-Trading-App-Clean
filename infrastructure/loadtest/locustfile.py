from __future__ import annotations

from pathlib import Path
import random
import sys
import time

from locust import LoadTestShape, User, events, task

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "backend"))

from app.core.config import Settings
from app.services.execution_queue_manager import ExecutionQueueManager
from app.services.redis_cache import RedisCache
from app.services.shard_manager import ShardManager
from app.services.signal_broadcaster import SignalBroadcaster


SETTINGS = Settings()
CACHE = RedisCache(SETTINGS.redis_url)
SHARD_MANAGER = ShardManager(SETTINGS)
QUEUE_MANAGER = ExecutionQueueManager(SETTINGS, CACHE, SHARD_MANAGER)
BROADCASTER = SignalBroadcaster(SETTINGS, CACHE, QUEUE_MANAGER)


def record(name: str, started: float, response_length: int = 0, exception: Exception | None = None) -> None:
    events.request.fire(
        request_type="redis",
        name=name,
        response_time=(time.perf_counter() - started) * 1000,
        response_length=response_length,
        exception=exception,
    )


class SubscriberUser(User):
    wait_time = lambda self: 0.01  # noqa: E731

    def on_start(self) -> None:
        self.user_id = f"locust-{random.randint(1, 10_000_000)}"
        tier = random.choice(["free", "pro", "vip", "institutional"])
        balance = {"free": 50.0, "pro": 1_000.0, "vip": 10_000.0, "institutional": 100_000.0}[tier]
        risk_profile = random.choice(["conservative", "moderate", "aggressive"])
        started = time.perf_counter()
        try:
            BROADCASTER.register_subscription(self.user_id, tier, balance, risk_profile)
            record("register_subscription", started)
        except Exception as exc:  # pragma: no cover
            record("register_subscription", started, exception=exc)

    @task(1)
    def refresh_subscription(self) -> None:
        started = time.perf_counter()
        try:
            payload = CACHE.get_json(f"subscription:{self.user_id}") or {}
            BROADCASTER.register_subscription(
                self.user_id,
                payload.get("tier", "free"),
                float(payload.get("balance", 0.0)),
                payload.get("risk_profile", "moderate"),
            )
            record("refresh_subscription", started)
        except Exception as exc:  # pragma: no cover
            record("refresh_subscription", started, exception=exc)


class SignalPublisherUser(User):
    wait_time = lambda self: random.uniform(0.2, 1.0)  # noqa: E731

    @task(3)
    def publish_signal(self) -> None:
        started = time.perf_counter()
        payload = {
            "signal_id": f"locust-signal-{int(time.time() * 1000)}-{random.randint(1, 100_000)}",
            "symbol": random.choice(["BTCUSDT", "ETHUSDT", "SOLUSDT"]),
            "strategy": random.choice(["TREND_FOLLOW", "BREAKOUT"]),
            "alpha_decision": {"final_score": random.choice([82.0, 87.0, 92.0])},
            "required_tier": random.choice(["free", "pro", "vip"]),
            "min_balance": random.choice([0.0, 100.0, 500.0]),
            "allowed_risk_profiles": random.choice(
                [["conservative", "moderate", "aggressive"], ["moderate", "aggressive"], ["aggressive"]]
            ),
        }
        try:
            response = BROADCASTER.publish_signal(payload)
            record("publish_signal", started, response_length=response["distribution"]["queued_total"])
        except Exception as exc:  # pragma: no cover
            record("publish_signal", started, exception=exc)


class QueueWorkerUser(User):
    wait_time = lambda self: 0.05  # noqa: E731

    def on_start(self) -> None:
        self.shard_id = random.randint(0, SETTINGS.execution_shard_count - 1)

    @task(5)
    def drain_queue(self) -> None:
        started = time.perf_counter()
        try:
            jobs = QUEUE_MANAGER.dequeue_batch(self.shard_id, limit=SETTINGS.execution_queue_batch_size)
            record("dequeue_batch", started, response_length=len(jobs))
        except Exception as exc:  # pragma: no cover
            record("dequeue_batch", started, exception=exc)


class HundredKShape(LoadTestShape):
    stages = [
        {"duration": 60, "users": 10_000, "spawn_rate": 500},
        {"duration": 180, "users": 50_000, "spawn_rate": 1_000},
        {"duration": 360, "users": 100_000, "spawn_rate": 1_500},
        {"duration": 480, "users": 100_000, "spawn_rate": 0},
        {"duration": 600, "users": 0, "spawn_rate": 2_000},
    ]

    def tick(self):
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time < stage["duration"]:
                return stage["users"], stage["spawn_rate"]
        return None
