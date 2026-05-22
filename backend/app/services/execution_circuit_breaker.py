from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from app.core.config import Settings
from app.services.redis_cache import RedisCache
from app.services.safety_state import SafetyStateService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExecutionCircuitDecision:
    allowed: bool
    reasons: list[str]
    details: dict[str, Any]


@dataclass
class ExecutionCircuitBreaker:
    settings: Settings
    cache: RedisCache

    def evaluate(self, *, trading_mode: str, symbol: str) -> ExecutionCircuitDecision:
        normalized_mode = str(trading_mode or "").lower()
        normalized_symbol = str(symbol or "").upper().strip()
        if not self.settings.execution_circuit_breaker_enabled:
            return ExecutionCircuitDecision(allowed=True, reasons=[], details={})
        if normalized_mode != "live" and not self.settings.execution_circuit_breaker_block_paper:
            return ExecutionCircuitDecision(allowed=True, reasons=[], details={"mode": normalized_mode})

        safety_state = SafetyStateService(settings=self.settings, cache=self.cache)
        reasons, snapshot = safety_state.unhealthy_reasons(trading_mode=normalized_mode)
        details: dict[str, Any] = {
            "mode": normalized_mode,
            "symbol": normalized_symbol,
            "safety_state": snapshot,
        }

        allowed = not reasons
        decision = ExecutionCircuitDecision(allowed=allowed, reasons=reasons, details=details)
        if not allowed:
            self.cache.increment("monitor:execution_circuit_breaker_open_total", ttl=int(self.settings.monitor_state_ttl_seconds))
            self.cache.set_json(
                "execution:circuit:last_block",
                {
                    "symbol": normalized_symbol,
                    "mode": normalized_mode,
                    "reasons": reasons,
                    "details": details,
                },
                ttl=int(self.settings.monitor_state_ttl_seconds),
            )
            logger.warning(
                "execution_circuit_breaker_blocked",
                extra={
                    "event": "execution_circuit_breaker_blocked",
                    "context": {
                        "symbol": normalized_symbol,
                        "mode": normalized_mode,
                        "reasons": reasons,
                        "details": details,
                    },
                },
            )
        return decision
