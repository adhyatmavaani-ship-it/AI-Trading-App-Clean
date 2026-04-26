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
    from app.api.routes import trading
    from app.middleware.auth import AuthMiddleware
    from app.services.container import get_container


class StubTradingOrchestrator:
    async def execute_signal(self, request):
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


class StubContainer:
    def __init__(self):
        self.trading_orchestrator = StubTradingOrchestrator()
        self.alerting_service = StubAlertingService()


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi is not installed")
class TradingRoutesTest(unittest.TestCase):
    def setUp(self):
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
        app.dependency_overrides[get_container] = lambda: StubContainer()
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


if __name__ == "__main__":
    unittest.main()
