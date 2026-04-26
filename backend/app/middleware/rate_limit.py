from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import get_settings
from app.services.redis_cache import RedisCache


logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        settings = get_settings()
        self.settings = settings
        self.minute_limit = max(int(settings.rate_limit_per_minute), 1)
        self.hour_limit = max(int(settings.rate_limit_per_hour), self.minute_limit)
        self.cache = RedisCache(settings.redis_url)
        self.trust_forwarded_for = settings.trust_forwarded_for

    async def dispatch(self, request: Request, call_next):
        if request.url.path in {"/health", "/v1/health", "/docs", "/redoc", "/openapi.json"} or request.url.path.startswith("/v1/health"):
            return await call_next(request)

        identity, source = self._identity(request)
        try:
            minute_key, minute_ttl = self._window_key(identity, source, window_seconds=60)
            hour_key, hour_ttl = self._window_key(identity, source, window_seconds=3600)
            minute_count = self.cache.increment(minute_key, ttl=minute_ttl)
            hour_count = self.cache.increment(hour_key, ttl=hour_ttl)
        except Exception:
            return await call_next(request)

        if minute_count > self.minute_limit or hour_count > self.hour_limit:
            retry_after = minute_ttl if minute_count > self.minute_limit else hour_ttl
            logger.warning(
                "rate_limit_exceeded",
                extra={
                    "event": "rate_limit_exceeded",
                    "context": {
                        "path": request.url.path,
                        "method": request.method,
                        "identity_source": source,
                        "identity": identity,
                        "minute_count": minute_count,
                        "minute_limit": self.minute_limit,
                        "hour_count": hour_count,
                        "hour_limit": self.hour_limit,
                        "retry_after_seconds": retry_after,
                    },
                },
            )
            return JSONResponse(
                status_code=429,
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit-Minute": str(self.minute_limit),
                    "X-RateLimit-Remaining-Minute": str(max(self.minute_limit - minute_count, 0)),
                    "X-RateLimit-Limit-Hour": str(self.hour_limit),
                    "X-RateLimit-Remaining-Hour": str(max(self.hour_limit - hour_count, 0)),
                },
                content={
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "message": "Rate limit exceeded",
                    "details": {
                        "identity_source": source,
                        "retry_after_seconds": retry_after,
                        "minute_limit": self.minute_limit,
                        "minute_remaining": max(self.minute_limit - minute_count, 0),
                        "hour_limit": self.hour_limit,
                        "hour_remaining": max(self.hour_limit - hour_count, 0),
                    },
                },
            )
        response = await call_next(request)
        response.headers["X-RateLimit-Limit-Minute"] = str(self.minute_limit)
        response.headers["X-RateLimit-Remaining-Minute"] = str(max(self.minute_limit - minute_count, 0))
        response.headers["X-RateLimit-Limit-Hour"] = str(self.hour_limit)
        response.headers["X-RateLimit-Remaining-Hour"] = str(max(self.hour_limit - hour_count, 0))
        return response

    def _identity(self, request: Request) -> tuple[str, str]:
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            return str(user_id), "user"
        return self._client_ip(request), "ip"

    def _client_ip(self, request: Request) -> str:
        if self.trust_forwarded_for:
            forwarded_for = request.headers.get("X-Forwarded-For", "")
            if forwarded_for:
                first_hop = forwarded_for.split(",")[0].strip()
                if first_hop:
                    return first_hop
            x_real_ip = request.headers.get("X-Real-IP", "").strip()
            if x_real_ip:
                return x_real_ip
            forwarded = request.headers.get("Forwarded", "")
            parsed_forwarded = self._parse_forwarded_header(forwarded)
            if parsed_forwarded:
                return parsed_forwarded
        return request.client.host if request.client else "unknown"

    def _parse_forwarded_header(self, header_value: str) -> str | None:
        if not header_value:
            return None
        first_part = header_value.split(",")[0]
        for token in first_part.split(";"):
            key, separator, value = token.strip().partition("=")
            if separator and key.lower() == "for":
                normalized = value.strip().strip('"')
                if normalized.startswith("[") and "]" in normalized:
                    return normalized[1:].split("]")[0]
                if ":" in normalized and normalized.count(":") == 1:
                    return normalized.split(":", 1)[0]
                return normalized
        return None

    def _window_key(self, identity: str, source: str, *, window_seconds: int) -> tuple[str, int]:
        now = int(time.time())
        bucket = now // window_seconds
        ttl = max(window_seconds - (now % window_seconds) + 1, 1)
        key = f"rate_limit:{source}:{identity}:{window_seconds}:{bucket}"
        return key, ttl
