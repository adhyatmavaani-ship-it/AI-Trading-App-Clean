from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.core.config import get_settings
from app.middleware.auth import get_user_id
from app.schemas.advanced_trading import (
    AiStrategyContextRequest,
    AiStrategyContextResponse,
    ChartOrderSyncRequest,
    ChartOrderSyncResponse,
    EncryptApiKeyRequest,
    EncryptedApiKeyResponse,
)
from app.services.advanced_trading_state import get_advanced_trading_state_repository
from app.services.api_key_crypto import ApiKeyEncryptionService


router = APIRouter(tags=["Advanced Trading State"])


@router.post("/keys/encrypt", response_model=EncryptedApiKeyResponse)
async def encrypt_user_api_key(request: Request, payload: EncryptApiKeyRequest) -> EncryptedApiKeyResponse:
    user_id = get_user_id(request)
    settings = get_settings()
    try:
        encrypted = ApiKeyEncryptionService(settings.user_api_key_encryption_secret).encrypt(
            payload.raw_api_key,
            associated_data=f"{user_id}:{payload.provider}",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    get_advanced_trading_state_repository().store_encrypted_api_key(
        user_id=user_id,
        provider=payload.provider,
        label=payload.label,
        key_hash=encrypted.key_hash,
        encrypted_key=encrypted.encrypted_key,
        encryption_iv=encrypted.encryption_iv,
        encryption_tag=encrypted.encryption_tag,
        key_preview=encrypted.key_preview,
    )
    return EncryptedApiKeyResponse(provider=payload.provider, label=payload.label, **encrypted.__dict__)


@router.post("/ai/strategy-context", response_model=AiStrategyContextResponse)
async def upsert_ai_strategy_context(payload: AiStrategyContextRequest) -> AiStrategyContextResponse:
    record = get_advanced_trading_state_repository().upsert_ai_strategy_context(payload)
    return AiStrategyContextResponse(**record)


@router.get("/ai/strategy-context/{ai_strategy_id}", response_model=AiStrategyContextResponse)
async def get_ai_strategy_context(ai_strategy_id: str) -> AiStrategyContextResponse:
    record = get_advanced_trading_state_repository().get_ai_strategy_context(ai_strategy_id)
    if record is None:
        raise HTTPException(status_code=404, detail="AI strategy context not found")
    return AiStrategyContextResponse(**record)


@router.get("/ai/strategy-context", response_model=list[AiStrategyContextResponse])
async def list_ai_strategy_contexts(limit: int = Query(default=25, ge=1, le=100)) -> list[AiStrategyContextResponse]:
    records = get_advanced_trading_state_repository().latest_ai_strategy_contexts(limit=limit)
    return [AiStrategyContextResponse(**record) for record in records]


@router.patch("/orders/chart-sync", response_model=ChartOrderSyncResponse)
async def sync_chart_order(request: Request, payload: ChartOrderSyncRequest) -> ChartOrderSyncResponse:
    user_id = get_user_id(request)
    try:
        record = get_advanced_trading_state_repository().sync_chart_order(user_id=user_id, payload=payload)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return ChartOrderSyncResponse(**record)


@router.get("/orders/chart-sync", response_model=list[ChartOrderSyncResponse])
async def list_chart_orders(
    request: Request,
    symbol: str | None = Query(default=None, min_length=2, max_length=32),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[ChartOrderSyncResponse]:
    user_id = get_user_id(request)
    records = get_advanced_trading_state_repository().list_chart_orders(user_id=user_id, symbol=symbol, limit=limit)
    return [ChartOrderSyncResponse(**record) for record in records]


@router.get("/orders/chart-sync/actions")
async def list_chart_order_testnet_actions(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict]:
    user_id = get_user_id(request)
    return get_advanced_trading_state_repository().list_chart_order_testnet_actions(user_id=user_id, limit=limit)
