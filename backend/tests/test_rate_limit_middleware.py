import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.middleware.rate_limit import RateLimitMiddleware
from app.services.redis_cache import RedisCache


class InMemoryRateLimitCache:
    def __init__(self):
        self.store = {}

    def increment(self, key, ttl):
        self.store[key] = int(self.store.get(key, 0)) + 1
        return self.store[key]


class RateLimitMiddlewareTest(unittest.TestCase):
    def setUp(self):
        get_settings.cache_clear()
        self.original_init = RedisCache.__init__
        self.original_increment = RedisCache.increment
        RedisCache.__init__ = lambda self, url: setattr(self, "client", None) or None
        RedisCache.increment = lambda _self, key, ttl: self.cache.increment(key, ttl)
        self.cache = InMemoryRateLimitCache()

    def tearDown(self):
        RedisCache.__init__ = self.original_init
        RedisCache.increment = self.original_increment
        get_settings.cache_clear()

    def _build_client(self, *, per_minute: int = 2, per_hour: int = 10) -> TestClient:
        settings = get_settings()
        settings.rate_limit_per_minute = per_minute
        settings.rate_limit_per_hour = per_hour
        settings.redis_url = "redis://unused"
        settings.trust_forwarded_for = True

        app = FastAPI()
        app.add_middleware(RateLimitMiddleware)

        @app.get("/secure")
        async def secure(request: Request):
            return {"user_id": getattr(request.state, "user_id", None)}

        @app.get("/v1/health")
        async def health():
            return {"status": "ok"}

        return TestClient(app)

    def test_uses_authenticated_user_id_when_present(self):
        client = self._build_client(per_minute=1, per_hour=5)

        @client.app.middleware("http")
        async def inject_user(request: Request, call_next):
            request.state.user_id = "alice"
            return await call_next(request)

        with patch("app.middleware.rate_limit.logger.warning") as warning_log:
            first = client.get("/secure", headers={"X-Forwarded-For": "10.0.0.1"})
            second = client.get("/secure", headers={"X-Forwarded-For": "10.0.0.2"})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertTrue(any(key.startswith("rate_limit:user:alice:") for key in self.cache.store))
        warning_log.assert_called_once()
        self.assertEqual(warning_log.call_args.args[0], "rate_limit_exceeded")
        self.assertEqual(
            warning_log.call_args.kwargs["extra"]["context"]["identity_source"],
            "user",
        )

    def test_falls_back_to_forwarded_ip_when_user_missing(self):
        client = self._build_client(per_minute=1, per_hour=5)

        with patch("app.middleware.rate_limit.logger.warning") as warning_log:
            first = client.get("/secure", headers={"X-Forwarded-For": "198.51.100.7, 10.0.0.5"})
            second = client.get("/secure", headers={"X-Forwarded-For": "198.51.100.7, 10.0.0.6"})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertTrue(any(key.startswith("rate_limit:ip:198.51.100.7:") for key in self.cache.store))
        warning_log.assert_called_once()
        self.assertEqual(warning_log.call_args.args[0], "rate_limit_exceeded")
        self.assertEqual(
            warning_log.call_args.kwargs["extra"]["context"]["identity_source"],
            "ip",
        )

    def test_health_is_excluded(self):
        client = self._build_client(per_minute=1, per_hour=1)

        first = client.get("/v1/health")
        second = client.get("/v1/health")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)


if __name__ == "__main__":
    unittest.main()
