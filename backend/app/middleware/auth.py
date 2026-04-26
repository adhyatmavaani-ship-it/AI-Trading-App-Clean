"""Authentication and authorization middleware."""

import hashlib
import logging
from typing import Callable

from fastapi import Request, Security
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError
from app.services.api_key_auth import ApiKeyAuthService


logger = logging.getLogger(__name__)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_api_key(api_key: str | None = Security(api_key_header)) -> str | None:
    """Expose the API key header to OpenAPI without replacing middleware auth."""
    return api_key


class AuthMiddleware(BaseHTTPMiddleware):
    """Validates API key/JWT and enforces authentication."""

    EXCLUDED_PATHS = {
        "/",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/health",
        "/health/live",
        "/health/ready",
        "/v1/health",
        "/v1/health/live",
        "/v1/health/ready",
    }
    EXCLUDED_PREFIXES = ("/public/", "/v1/public/")

    def __init__(self, app):
        super().__init__(app)
        self.settings = get_settings()
        self.auth_service = ApiKeyAuthService(self.settings)

    async def dispatch(self, request: Request, call_next: Callable):
        path = request.url.path.rstrip("/") or "/"
        api_key = request.headers.get("X-API-Key") or request.headers.get("Authorization", "")
        auth_scheme = "X-API-Key"
        if api_key.startswith("Bearer "):
            api_key = api_key[7:]
            auth_scheme = "Bearer"
        api_key = api_key.strip()

        # Skip required auth for health checks and documentation, but preserve identity when a valid credential is provided.
        if path in self.EXCLUDED_PATHS or path.startswith(self.EXCLUDED_PREFIXES):
            if api_key:
                principal = self.auth_service.authenticate(api_key)
                if principal is not None:
                    self._set_request_context(request, principal, api_key)
            return await call_next(request)

        if not api_key:
            self._log_failure(request, reason="missing_credentials", auth_scheme=auth_scheme)
            return JSONResponse(
                status_code=401,
                content={
                    "error_code": "MISSING_API_KEY",
                    "message": "Missing X-API-Key header or Authorization bearer token",
                    "details": {},
                },
            )

        principal = self.auth_service.authenticate(api_key)
        if principal is None:
            self._log_failure(request, reason="invalid_or_expired_api_key", auth_scheme=auth_scheme, api_key=api_key)
            return JSONResponse(
                status_code=401,
                content={
                    "error_code": "INVALID_API_KEY",
                    "message": "Invalid or expired API key",
                    "details": {},
                },
            )

        self._set_request_context(request, principal, api_key)
        response = await call_next(request)
        return response

    def _set_request_context(self, request: Request, principal, api_key: str) -> None:
        request.state.user_id = principal.user_id
        request.state.authenticated_user_id = principal.user_id
        request.state.api_key = api_key
        request.state.auth_source = principal.auth_source
        request.state.api_key_id = principal.key_id
        request.state.auth_principal_type = principal.principal_type
        request.state.auth_can_execute_for_users = principal.can_execute_for_users

    def _log_failure(
        self,
        request: Request,
        *,
        reason: str,
        auth_scheme: str,
        api_key: str | None = None,
    ) -> None:
        fingerprint = None
        if api_key:
            fingerprint = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:12]
        logger.warning(
            "authentication_failed",
            extra={
                "event": "authentication_failed",
                "context": {
                    "reason": reason,
                    "auth_scheme": auth_scheme,
                    "path": request.url.path,
                    "method": request.method,
                    "client_ip": request.client.host if request.client else "unknown",
                    "api_key_fingerprint": fingerprint,
                },
            },
        )


def get_user_id(request: Request) -> str:
    """Extract authenticated user ID from request context."""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise AuthenticationError("User context not found. Check auth middleware is installed.")
    return user_id


def can_execute_for_users(request: Request) -> bool:
    """Return whether the authenticated principal can execute trades for another user."""
    return bool(getattr(request.state, "auth_can_execute_for_users", False))
