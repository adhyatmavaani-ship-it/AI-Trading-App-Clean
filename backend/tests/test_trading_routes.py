import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ModuleNotFoundError:
    FASTAPI_AVAILABLE = False

if FASTAPI_AVAILABLE:
    from app.core.config import Settings
    from app.api.routes import trading
    from app.middleware.auth import AuthMiddleware
    from app.services.container import get_container
    from app.services.execution_idempotency import ExecutionIdempotencyService
    from app.services.redis_cache import RedisCache


class StubTradingOrchestrator:
    def __init__(self, failure: Exception | None = None):
        self.failure = failure

    async def execute_signal(self, request):
        if self.failure is not None:
            raise self.failure
        return {
            "trade_id": "trade-1",
            "status": "EXECUTED",
            "trading_mode": "paper",
            "symbol": request.symbol,
            "side": request.side,
            "executed_price": 100.0,
            "executed_quantity": request.quantity or 1.0,
            "stop_loss": 95.0,
            "trailing_stop_pct": 0.004,
            "take_profit": 110.0,
            "fee_paid": 0.1,
            "slippage_bps": 10.0,
            "filled_ratio": 1.0,
            "duplicate_signal": False,
            "rollout_capital_fraction": 1.0,
            "explanation": "ok",
            "alpha_score": 0.0,
            "macro_bias_multiplier": 1.0,
            "macro_bias_regime": "NEUTRAL",
        }


class StubAlertingService:
    async def send(self, *args, **kwargs):
        return None


class StubCircuitDecision:
    def __init__(self, allowed: bool, reasons: list[str] | None = None):
        self.allowed = allowed
        self.reasons = reasons or []
        self.details = {"source": "test"}


class StubExecutionCircuitBreaker:
    def __init__(self, decision: StubCircuitDecision):
        self.decision = decision

    def evaluate(self, *, trading_mode: str, symbol: str):
        return self.decision


class StubContainer:
    def __init__(
        self,
        failure: Exception | None = None,
        circuit_decision: StubCircuitDecision | None = None,
        idempotency_service: object | None = None,
        trading_mode: str = "paper",
    ):
        self.trading_orchestrator = StubTradingOrchestrator(failure=failure)
        self.alerting_service = StubAlertingService()
        self.settings = type("Settings", (), {"trading_mode": trading_mode})()
        if idempotency_service is not None:
            self.execution_idempotency_service = idempotency_service
        if circuit_decision is not None:
            self.execution_circuit_breaker = StubExecutionCircuitBreaker(circuit_decision)
            self.settings = type("Settings", (), {"trading_mode": "live"})()


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi is not installed")
class TradingRoutesTest(unittest.TestCase):
    def setUp(self):
        self._build_app()

    def _build_app(self, failure: Exception | None = None) -> None:
        from app.core.config import get_settings

        get_settings.cache_clear()
        settings = get_settings()
        settings.auth_api_keys_json = (
            '[{"api_key":"route-token","user_id":"alice","key_id":"alice-key"},'
            '{"api_key":"system-route-token","user_id":"system-executor","key_id":"system-key","principal_type":"system_executor","can_execute_for_users":true}]'
        )
        settings.firestore_project_id = ""
        settings.auth_cache_ttl_seconds = 60

        app = FastAPI()
        app.add_middleware(AuthMiddleware)
        app.include_router(trading.router, prefix="/v1")
        app.dependency_overrides[get_container] = lambda: StubContainer(failure=failure)
        self.app = app
        self.client = TestClient(app)

    def tearDown(self):
        self.app.dependency_overrides.clear()
        from app.core.config import get_settings

        get_settings.cache_clear()

    def test_execute_trade_rejects_user_impersonation(self):
        response = self.client.post(
            "/v1/trading/execute",
            headers={"X-API-Key": "route-token"},
            json={
                "user_id": "mallory",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "quantity": 1.0,
                "confidence": 0.8,
                "reason": "test",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["detail"]["error_code"],
            "UNAUTHORIZED_TRADE_EXECUTION",
        )

    def test_execute_trade_accepts_authenticated_user(self):
        response = self.client.post(
            "/v1/trading/execute",
            headers={"X-API-Key": "route-token"},
            json={
                "user_id": "alice",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "quantity": 1.0,
                "confidence": 0.8,
                "reason": "test",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["trade_id"], "trade-1")

    def test_execute_trade_blocks_shield_size_override(self):
        response = self.client.post(
            "/v1/trading/execute",
            headers={"X-API-Key": "route-token"},
            json={
                "user_id": "alice",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "requested_notional": 20001.0,
                "confidence": 0.8,
                "reason": "test",
                "feature_snapshot": {
                    "shield_required": 1.0,
                    "shield_account_balance": 100000.0,
                    "shield_entry_price": 100.0,
                    "shield_stop_loss": 95.0,
                    "shield_take_profit": 110.0,
                },
            },
        )

        self.assertEqual(response.status_code, 403)
        payload = response.json()["detail"]
        self.assertEqual(payload["error_code"], "POSITION_SIZE_EXCEEDS_RISK_LIMIT")
        self.assertEqual(payload["details"]["auto_quantity"], 200.0)

    def test_execute_trade_accepts_system_executor_for_other_user(self):
        response = self.client.post(
            "/v1/trading/execute",
            headers={
                "X-API-Key": "system-route-token",
                "X-Execution-User-Id": "mallory",
            },
            json={
                "user_id": "mallory",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "quantity": 1.0,
                "confidence": 0.8,
                "reason": "test",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["trade_id"], "trade-1")

    def test_execute_trade_rejects_system_executor_when_header_mismatches_target_user(self):
        response = self.client.post(
            "/v1/trading/execute",
            headers={
                "X-API-Key": "system-route-token",
                "X-Execution-User-Id": "alice",
            },
            json={
                "user_id": "mallory",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "quantity": 1.0,
                "confidence": 0.8,
                "reason": "test",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["detail"]["error_code"],
            "EXECUTION_USER_MISMATCH",
        )

    def test_execute_trade_maps_low_confidence_rejection(self):
        self.app.dependency_overrides[get_container] = lambda: StubContainer(
            failure=ValueError("Trade confidence is below the strict execution floor")
        )

        response = self.client.post(
            "/v1/trading/execute",
            headers={"X-API-Key": "route-token"},
            json={
                "user_id": "alice",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "quantity": 1.0,
                "confidence": 0.42,
                "reason": "test",
            },
        )

        self.assertEqual(response.status_code, 403)
        payload = response.json()["detail"]
        self.assertEqual(payload["error_code"], "CONFIDENCE_TOO_LOW")
        self.assertEqual(payload["details"]["symbol"], "BTCUSDT")
        self.assertIn("correlation_id", payload["details"])

    def test_execute_trade_maps_broker_unavailable_runtime_error(self):
        self.app.dependency_overrides[get_container] = lambda: StubContainer(
            failure=RuntimeError("No exchange clients available for execution")
        )

        response = self.client.post(
            "/v1/trading/execute",
            headers={"X-API-Key": "route-token"},
            json={
                "user_id": "alice",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "quantity": 1.0,
                "confidence": 0.8,
                "reason": "test",
            },
        )

        self.assertEqual(response.status_code, 500)
        payload = response.json()["detail"]
        self.assertEqual(payload["error_code"], "BROKER_UNAVAILABLE")
        self.assertEqual(payload["details"]["symbol"], "BTCUSDT")

    def test_execute_trade_returns_graceful_circuit_breaker_state(self):
        self.app.dependency_overrides[get_container] = lambda: StubContainer(
            circuit_decision=StubCircuitDecision(
                allowed=False,
                reasons=["market feed stale", "broker reconciliation mismatch"],
            )
        )

        response = self.client.post(
            "/v1/trading/execute",
            headers={"X-API-Key": "route-token"},
            json={
                "user_id": "alice",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "quantity": 1.0,
                "confidence": 0.8,
                "reason": "test",
            },
        )

        self.assertEqual(response.status_code, 409)
        payload = response.json()["detail"]
        self.assertEqual(payload["error_code"], "EXECUTION_CIRCUIT_OPEN")
        self.assertEqual(payload["message"], "Execution temporarily paused while safety checks complete")
        self.assertEqual(payload["details"]["state"], "execution temporarily paused")
        self.assertIn("market feed stale", payload["details"]["reasons"])

    def test_execute_trade_replays_duplicate_idempotency_key(self):
        cache = RedisCache("")
        service = ExecutionIdempotencyService(
            settings=Settings(redis_url="", execution_idempotency_ttl_seconds=60),
            cache=cache,
        )
        self.app.dependency_overrides[get_container] = lambda: StubContainer(
            idempotency_service=service,
            trading_mode="live",
        )
        payload = {
            "user_id": "alice",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "quantity": 1.0,
            "confidence": 0.8,
            "reason": "test",
        }

        first = self.client.post(
            "/v1/trading/execute",
            headers={"X-API-Key": "route-token", "X-Idempotency-Key": "retry-key-1"},
            json=payload,
        )
        second = self.client.post(
            "/v1/trading/execute",
            headers={"X-API-Key": "route-token", "X-Idempotency-Key": "retry-key-1"},
            json=payload,
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["trade_id"], "trade-1")
        self.assertTrue(second.json()["duplicate_signal"])


if __name__ == "__main__":
    unittest.main()
