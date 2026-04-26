"""Circuit breaker pattern implementation for external API protection."""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, TypeVar

from app.core.exceptions import CircuitBreakerOpenError

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitBreakerState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Blocking calls
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5  # Failures before opening
    recovery_timeout_seconds: int = 60  # Time before attempting recovery
    expected_exception: type = Exception
    max_half_open_calls: int = 1  # How many calls to test in half-open state


class CircuitBreaker:
    """
    Circuit breaker to protect external API calls.
    Prevents cascading failures by failing fast when service is degraded.
    """

    def __init__(self, name: str, config: CircuitBreakerConfig | None = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.success_count_in_half_open = 0
        self._lock = asyncio.Lock()

    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function with circuit breaker protection."""
        async with self._lock:
            if self.state == CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitBreakerState.HALF_OPEN
                    self.success_count_in_half_open = 0
                    logger.info(
                        f"Circuit breaker {self.name} transitioning to HALF_OPEN",
                        extra={"circuit_breaker": self.name, "state": "half_open"},
                    )
                else:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker {self.name} is OPEN. Service unavailable.",
                        error_code="CIRCUIT_BREAKER_OPEN",
                        details={"service": self.name},
                    )

        try:
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            await self._on_success()
            return result
        except self.config.expected_exception as e:
            await self._on_failure()
            raise

    async def _on_success(self):
        """Handle successful call."""
        async with self._lock:
            self.failure_count = 0
            if self.state == CircuitBreakerState.HALF_OPEN:
                self.success_count_in_half_open += 1
                if self.success_count_in_half_open >= self.config.max_half_open_calls:
                    self.state = CircuitBreakerState.CLOSED
                    logger.info(
                        f"Circuit breaker {self.name} recovered - CLOSED",
                        extra={"circuit_breaker": self.name, "state": "closed"},
                    )

    async def _on_failure(self):
        """Handle failed call."""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            logger.warning(
                f"Circuit breaker {self.name} failure",
                extra={
                    "circuit_breaker": self.name,
                    "failure_count": self.failure_count,
                    "threshold": self.config.failure_threshold,
                },
            )
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitBreakerState.OPEN
                logger.error(
                    f"Circuit breaker {self.name} OPEN - threshold exceeded",
                    extra={"circuit_breaker": self.name, "state": "open"},
                )

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self.last_failure_time is None:
            return True
        elapsed = time.time() - self.last_failure_time
        return elapsed >= self.config.recovery_timeout_seconds

    def get_state(self) -> dict:
        """Get current breaker state for monitoring."""
        return {
            "service": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time,
        }
