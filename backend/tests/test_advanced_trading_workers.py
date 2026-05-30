import asyncio

from app.schemas.advanced_trading import ChartOrderSyncRequest
from app.services.advanced_trading_state import AdvancedTradingStateRepository
from app.services.api_key_crypto import ApiKeyEncryptionService
from app.services.chart_execution_bridge import ChartExecutionBridgeWorker
from app.services.ml_signal_pipeline import MlSignalPipelineWorker


class FakeTradingUpdateManager:
    def __init__(self) -> None:
        self.broadcasts = []
        self.performance_broadcasts = []

    async def broadcast_chart_order_action(self, *, user_id: str, action: dict):
        self.broadcasts.append({"user_id": user_id, "action": action})
        return 1

    async def broadcast_strategy_performance_update(self, *, user_id: str, snapshot: dict):
        self.performance_broadcasts.append({"user_id": user_id, "snapshot": snapshot})
        return 1


def test_ml_signal_pipeline_upserts_ai_strategy_context(tmp_path) -> None:
    repository = AdvancedTradingStateRepository(tmp_path / "state.db")
    worker = MlSignalPipelineWorker(repository=repository, interval_seconds=0.1)

    record = asyncio.run(worker.run_once())

    assert record["slug"] == "ml-signal-btcusdt"
    assert record["risk_context"]["advisory_only"] is True
    assert record["risk_context"]["execution_mutation"] is False
    assert record["signal_context"]["forecast"]
    assert record["signal_context"]["signal_markers"][0]["symbol"] == "BTCUSDT"


def test_chart_execution_bridge_consumes_chart_sync_into_mock_action(tmp_path) -> None:
    repository = AdvancedTradingStateRepository(tmp_path / "state.db")
    encrypted = ApiKeyEncryptionService(ApiKeyEncryptionService.generate_master_key()).encrypt(
        "binance-testnet-key-material",
        associated_data="user-1:binance",
    )
    repository.store_encrypted_api_key(
        user_id="user-1",
        provider="binance",
        label="Testnet",
        key_hash=encrypted.key_hash,
        encrypted_key=encrypted.encrypted_key,
        encryption_iv=encrypted.encryption_iv,
        encryption_tag=encrypted.encryption_tag,
        key_preview=encrypted.key_preview,
    )
    order = repository.sync_chart_order(
        user_id="user-1",
        payload=ChartOrderSyncRequest(
            symbol="ETHUSDT",
            side="BUY",
            order_type="LIMIT",
            limit_price=3500.0,
            quantity=0.2,
            is_ai_trailing=True,
            status="STAGED",
        ),
    )
    websocket_manager = FakeTradingUpdateManager()
    worker = ChartExecutionBridgeWorker(
        repository=repository,
        websocket_manager=websocket_manager,
        mode="testnet",
        interval_seconds=0.1,
    )

    actions = asyncio.run(worker.run_once())

    assert len(actions) == 1
    assert actions[0]["chart_order_id"] == order["chart_order_id"]
    assert actions[0]["mode"] == "testnet"
    assert actions[0]["action_type"] == "SYNC_MOCK_TESTNET_ORDER"
    assert actions[0]["credential_provider"] == "binance"
    assert actions[0]["credential_key_preview"] == encrypted.key_preview
    assert actions[0]["action_payload"]["live_broker_submission"] is False
    assert websocket_manager.broadcasts[0]["user_id"] == "user-1"
    assert websocket_manager.broadcasts[0]["action"]["action_id"] == actions[0]["action_id"]
    assert websocket_manager.performance_broadcasts[0]["user_id"] == "user-1"
    assert websocket_manager.performance_broadcasts[0]["snapshot"]["advisory_only"] is True
    assert websocket_manager.performance_broadcasts[0]["snapshot"]["simulation_only"] is True
    assert websocket_manager.performance_broadcasts[0]["snapshot"]["live_broker_submission"] is False


def test_chart_execution_bridge_does_not_create_live_execution_path(tmp_path) -> None:
    repository = AdvancedTradingStateRepository(tmp_path / "state.db")
    repository.sync_chart_order(
        user_id="user-1",
        payload=ChartOrderSyncRequest(
            symbol="SOLUSDT",
            side="SELL",
            order_type="TAKE_PROFIT",
            take_profit=250.0,
            quantity=1.0,
            status="DRAFT",
        ),
    )
    websocket_manager = FakeTradingUpdateManager()
    worker = ChartExecutionBridgeWorker(
        repository=repository,
        websocket_manager=websocket_manager,
        mode="mock",
        interval_seconds=0.1,
    )

    actions = asyncio.run(worker.run_once())

    assert actions[0]["action_type"] == "IGNORE_NON_EXECUTABLE_CHART_STATE"
    assert actions[0]["action_payload"]["accepted"] is True
    assert actions[0]["action_payload"]["live_broker_submission"] is False
    assert websocket_manager.broadcasts[0]["action"]["action_type"] == "IGNORE_NON_EXECUTABLE_CHART_STATE"
    assert websocket_manager.performance_broadcasts[0]["snapshot"]["advisory_only"] is True
