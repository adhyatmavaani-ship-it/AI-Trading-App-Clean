from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.services.firestore_repo import FirestoreRepository
from app.services.narrative_macro_intelligence import NarrativeMacroIntelligenceEngine
from app.services.redis_cache import RedisCache
from app.services.redis_state_manager import RedisStateManager


async def run_macro_worker() -> None:
    settings = get_settings()
    cache = RedisCache(settings.redis_url)
    redis_state_manager = RedisStateManager(settings, cache)
    firestore = FirestoreRepository(settings.firestore_project_id)
    engine = NarrativeMacroIntelligenceEngine(
        settings=settings,
        redis_state_manager=redis_state_manager,
        firestore=firestore,
    )
    await engine.run_macro_worker(symbol="BTCUSDT", poll_seconds=300)


def run() -> None:
    asyncio.run(run_macro_worker())
