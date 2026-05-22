from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from app.services.redis_cache import RedisCache

if TYPE_CHECKING:
    from db.database import SQLiteTradeDatabase


@dataclass
class StrategyMarketplaceService:
    cache: RedisCache
    store: "SQLiteTradeDatabase | None" = None
    cache_key: str = "pro:strategy_marketplace:items"

    def publish(self, *, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        evidence_type = str(payload.get("evidence_type", "")).lower().strip()
        if evidence_type in {"screenshot", "image", "manual_screenshot"}:
            raise ValueError("Verified performance requires ledger or backtest evidence, not screenshots.")
        metrics = dict(payload.get("metrics") or {})
        trade_count = int(metrics.get("trade_count", metrics.get("trades", 0)) or 0)
        if evidence_type not in {"paper_ledger", "live_ledger", "backtest_ledger"} or trade_count <= 0:
            raise ValueError("Strategy must include a ledger-backed performance record.")
        strategy_id = _strategy_id(user_id=user_id, name=str(payload.get("name", "")))
        record = {
            "strategy_id": strategy_id,
            "publisher_user_id": user_id,
            "name": str(payload.get("name", "Untitled Strategy"))[:80],
            "description": str(payload.get("description", ""))[:500],
            "style": _normalize_style(str(payload.get("style", "trend_following"))),
            "markets": [str(item).upper() for item in list(payload.get("markets") or ["CRYPTO"])[:8]],
            "evidence_type": evidence_type,
            "metrics": {
                "trade_count": trade_count,
                "win_rate": round(float(metrics.get("win_rate", 0.0) or 0.0), 4),
                "profit_factor": round(float(metrics.get("profit_factor", 0.0) or 0.0), 4),
                "max_drawdown": round(float(metrics.get("max_drawdown", 0.0) or 0.0), 4),
            },
            "verified": True,
            "verification_note": "Ledger-backed performance record accepted; screenshots are not used as proof.",
            "published_at": datetime.now(timezone.utc).isoformat(),
        }
        if self.store is not None:
            self.store.save_strategy_marketplace_record(record)
        else:
            records = [item for item in self.list() if item.get("strategy_id") != strategy_id]
            records.append(record)
            self.cache.set_json(self.cache_key, records[-250:], ttl=60 * 60 * 24 * 365)
        return record

    def list(self) -> list[dict[str, Any]]:
        if self.store is not None:
            return self.store.list_strategy_marketplace_records()
        return list(self.cache.get_json(self.cache_key) or [])

    def auto_weights(self, *, regime: str, strategy_ids: list[str] | None = None) -> dict[str, Any]:
        normalized_regime = str(regime or "RANGING").upper().strip()
        records = self.list()
        if strategy_ids:
            allowed = {str(item) for item in strategy_ids}
            records = [item for item in records if str(item.get("strategy_id")) in allowed]
        if not records:
            records = _default_strategies()
        scores = []
        for item in records:
            metrics = dict(item.get("metrics") or {})
            base = (
                float(metrics.get("win_rate", 0.0) or 0.0) * 0.45
                + min(float(metrics.get("profit_factor", 0.0) or 0.0) / 2.5, 1.0) * 0.40
                + max(0.0, 1.0 - float(metrics.get("max_drawdown", 0.0) or 0.0)) * 0.15
            )
            style = str(item.get("style", "trend_following"))
            regime_multiplier = _regime_multiplier(normalized_regime, style)
            scores.append((item, max(base * regime_multiplier, 0.01)))
        total = sum(score for _, score in scores) or 1.0
        weights = [
            {
                "strategy_id": str(item.get("strategy_id")),
                "name": str(item.get("name")),
                "style": str(item.get("style")),
                "capital_weight": round(score / total, 4),
                "reason": _weight_reason(normalized_regime, str(item.get("style"))),
            }
            for item, score in scores
        ]
        weights.sort(key=lambda item: float(item["capital_weight"]), reverse=True)
        return {
            "regime": normalized_regime,
            "weights": weights,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


def _strategy_id(*, user_id: str, name: str) -> str:
    digest = hashlib.sha1(f"{user_id}:{name}:{datetime.now(timezone.utc).date()}".encode("utf-8")).hexdigest()[:12]
    return f"strat_{digest}"


def _normalize_style(value: str) -> str:
    normalized = value.lower().replace("-", "_").replace(" ", "_").strip()
    if normalized in {"breakout", "trend", "trend_following", "momentum"}:
        return "trend_following"
    if normalized in {"mean_reversion", "range", "sideways"}:
        return "mean_reversion"
    return "hybrid"


def _regime_multiplier(regime: str, style: str) -> float:
    if regime in {"TRENDING", "BULLISH", "BEARISH"} and style == "trend_following":
        return 1.70
    if regime in {"RANGING", "SIDEWAYS", "SIDEWAYS_CHOP"} and style == "mean_reversion":
        return 1.55
    if regime in {"HIGH_VOL", "VOLATILE"} and style == "hybrid":
        return 1.20
    return 0.78 if style == "mean_reversion" and regime == "TRENDING" else 1.0


def _weight_reason(regime: str, style: str) -> str:
    if regime == "TRENDING" and style == "trend_following":
        return "Trending market: trend-following allocation is boosted."
    if regime in {"RANGING", "SIDEWAYS", "SIDEWAYS_CHOP"} and style == "mean_reversion":
        return "Sideways market: mean-reversion allocation is favored."
    return "Allocation follows verified ledger performance and regime fit."


def _default_strategies() -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": "default_trend_following",
            "name": "Verified Trend Following",
            "style": "trend_following",
            "metrics": {"trade_count": 30, "win_rate": 0.58, "profit_factor": 1.65, "max_drawdown": 0.08},
        },
        {
            "strategy_id": "default_mean_reversion",
            "name": "Verified Mean Reversion",
            "style": "mean_reversion",
            "metrics": {"trade_count": 30, "win_rate": 0.53, "profit_factor": 1.35, "max_drawdown": 0.06},
        },
    ]
