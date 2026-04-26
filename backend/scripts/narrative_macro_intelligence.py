from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app.core.config import Settings
from app.services.firestore_repo import FirestoreRepository
from app.services.narrative_macro_intelligence import NarrativeMacroIntelligenceEngine
from app.services.redis_cache import RedisCache
from app.services.redis_state_manager import RedisStateManager


async def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python backend/scripts/narrative_macro_intelligence.py <market-payload.json>")
        return 1

    payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    settings = Settings()
    cache = RedisCache(settings.redis_url)
    redis_state_manager = RedisStateManager(settings, cache)
    firestore = FirestoreRepository(settings.firestore_project_id)
    engine = NarrativeMacroIntelligenceEngine(
        settings=settings,
        redis_state_manager=redis_state_manager,
        firestore=firestore,
    )
    report = await engine.analyze_market(
        symbol=payload["symbol"],
        social_metrics=payload["social_metrics"],
        onchain_metrics=payload["onchain_metrics"],
        macro_metrics=payload["macro_metrics"],
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
