"""Custom exception hierarchy for trading system."""

from typing import Any


class TradingSystemException(Exception):
    """Base exception for all trading system errors."""

    status_code = 400

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to API response dict."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class AuthenticationError(TradingSystemException):
    """Raised when authentication fails."""

    status_code = 401


class AuthorizationError(TradingSystemException):
    """Raised when user lacks required permissions."""

    status_code = 403


class ValidationError(TradingSystemException):
    """Raised when input validation fails."""

    status_code = 400


class InsufficientBalanceError(TradingSystemException):
    """Raised when account balance insufficient for trade."""

    status_code = 400


class RiskLimitExceededError(TradingSystemException):
    """Raised when trade would violate risk limits."""

    status_code = 403


class ExecutionError(TradingSystemException):
    """Raised when order execution fails."""

    status_code = 500


class MarketDataError(TradingSystemException):
    """Raised when market data fetch/processing fails."""

    status_code = 503


class ExchangeError(TradingSystemException):
    """Raised when exchange API returns error."""

    status_code = 502


class CircuitBreakerOpenError(TradingSystemException):
    """Raised when circuit breaker is open for external service."""

    status_code = 503


class ServiceUnavailableError(TradingSystemException):
    """Raised when required service is unavailable."""

    status_code = 503


class ConfigurationError(TradingSystemException):
    """Raised when system configuration is invalid."""

    status_code = 500


class StateError(TradingSystemException):
    """Raised when operation violates state machine logic."""

    status_code = 409
