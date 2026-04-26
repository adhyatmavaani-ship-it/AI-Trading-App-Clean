from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.config import get_settings
from app.services.redis_cache import RedisCache
from app.services.system_monitor import SystemMonitorService

logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    EXCLUDED_LOG_PATHS = {"/health", "/v1/health", "/docs", "/redoc", "/openapi.json"}
    EXCLUDED_LOG_PREFIXES = ("/health/", "/v1/health/")

    def __init__(self, app):
        super().__init__(app)
        settings = get_settings()
        self.monitor = SystemMonitorService(settings, RedisCache(settings.redis_url))

    async def dispatch(self, request: Request, call_next):
        # Generate or extract correlation ID (for request tracing)
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            user_id = getattr(request.state, "user_id", "anonymous")
            try:
                self.monitor.increment_error()
            except Exception:
                pass
            logger.error(
                "request_failed",
                extra={
                    "event": "request_failed",
                    "context": {
                        "correlation_id": correlation_id,
                        "user_id": user_id,
                        "path": request.url.path,
                        "method": request.method,
                        "error": str(exc)[:200],
                    },
                },
            )
            raise
            
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        try:
            self.monitor.record_latency(latency_ms)
        except Exception:
            pass

        if self._should_log_request(request.url.path):
            user_id = getattr(request.state, "user_id", "anonymous")
            logger.info(
                "request_completed",
                extra={
                    "event": "request_completed",
                    "context": {
                        "correlation_id": correlation_id,
                        "user_id": user_id,
                        "path": request.url.path,
                        "method": request.method,
                        "status_code": response.status_code,
                        "latency_ms": latency_ms,
                    },
                },
            )
        
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Process-Time-Ms"] = str(latency_ms)
        return response

    def _should_log_request(self, path: str) -> bool:
        return path not in self.EXCLUDED_LOG_PATHS and not path.startswith(self.EXCLUDED_LOG_PREFIXES)
