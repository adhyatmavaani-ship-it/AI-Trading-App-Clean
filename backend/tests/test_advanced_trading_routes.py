from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
import pytest

from app.api.routes.advanced_trading import router
from app.core.config import get_settings
from app.services.advanced_trading_state import reset_advanced_trading_state_repository
from app.services.api_key_crypto import ApiKeyEncryptionService


@pytest.fixture(autouse=True)
def _clear_settings_cache_after_test():
    yield
    get_settings.cache_clear()
    reset_advanced_trading_state_repository()


def _client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("PRO_STORAGE_PATH", str(tmp_path / "advanced_trading_state.db"))
    monkeypatch.setenv("USER_API_KEY_ENCRYPTION_SECRET", ApiKeyEncryptionService.generate_master_key())
    get_settings.cache_clear()
    reset_advanced_trading_state_repository()

    app = FastAPI()

    @app.middleware("http")
    async def set_user_context(request: Request, call_next):
        request.state.user_id = "user-test-1"
        return await call_next(request)

    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


def test_encrypt_api_key_route_stores_encrypted_material(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/keys/encrypt",
        json={
            "provider": "binance",
            "label": "Primary Binance",
            "raw_api_key": "binance_live_key_material_123456",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "binance"
    assert body["label"] == "Primary Binance"
    assert body["key_preview"] == "bina...3456"
    assert body["encrypted_key"] != "binance_live_key_material_123456"
    assert body["encryption_iv"]
    assert body["encryption_tag"]


def test_ai_strategy_context_round_trip_is_stable(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/ai/strategy-context",
        json={
            "slug": "Crypto Momentum Pro",
            "version": "v1",
            "display_name": "Crypto Momentum Pro",
            "model_family": "ensemble",
            "metrics": {"win_rate": 0.71, "profit_factor": 1.8},
            "risk_context": {"max_risk_per_trade": 0.01},
            "signal_context": {"reason": "BTC trend aligned"},
        },
    )

    assert response.status_code == 200
    created = response.json()
    assert created["slug"] == "crypto-momentum-pro"
    assert created["metrics"]["win_rate"] == 0.71

    fetched = client.get(f"/api/v1/ai/strategy-context/{created['ai_strategy_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["ai_strategy_id"] == created["ai_strategy_id"]
    assert fetched.json()["signal_context"]["reason"] == "BTC trend aligned"


def test_chart_order_sync_is_user_scoped_and_advisory_only(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.patch(
        "/api/v1/orders/chart-sync",
        json={
            "workspace_mode": "EXECUTION_MODE",
            "symbol": "btcusdt",
            "exchange": "binance",
            "side": "BUY",
            "order_type": "LIMIT",
            "limit_price": 68500.25,
            "stop_loss": 67200.0,
            "take_profit": 70800.0,
            "quantity": 0.05,
            "is_ai_trailing": True,
            "status": "STAGED",
            "client_revision": 4,
            "chart_context": {"line_source": "drag", "timeframe": "15m"},
        },
    )

    assert response.status_code == 200
    synced = response.json()
    assert synced["user_id"] == "user-test-1"
    assert synced["symbol"] == "BTCUSDT"
    assert synced["exchange"] == "BINANCE"
    assert synced["is_ai_trailing"] is True
    assert synced["status"] == "STAGED"
    assert synced["chart_context"]["line_source"] == "drag"

    listed = client.get("/api/v1/orders/chart-sync?symbol=BTCUSDT")
    assert listed.status_code == 200
    assert listed.json()[0]["chart_order_id"] == synced["chart_order_id"]
