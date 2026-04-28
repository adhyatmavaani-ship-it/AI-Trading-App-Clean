from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import median

from app.core.config import Settings
from app.services.market_data import MarketDataService
from app.services.redis_cache import RedisCache


@dataclass
class ScannerService:
    settings: Settings
    cache: RedisCache
    market_data: MarketDataService

    state_cache_key: str = "scanner:state"

    async def state(self, *, force_refresh: bool = False) -> dict[str, object]:
        now = datetime.now(timezone.utc)
        cached = self.cache.get_json(self.state_cache_key) or {}
        refreshed_at = self._parse_datetime(cached.get("refreshed_at"))
        next_rotation_at = self._parse_datetime(cached.get("next_rotation_at"))
        refresh_due = (
            force_refresh
            or refreshed_at is None
            or (now - refreshed_at).total_seconds() >= max(60, self.settings.scanner_refresh_minutes * 60)
        )
        rotation_due = (
            force_refresh
            or not cached.get("active_symbols")
            or next_rotation_at is None
            or now >= next_rotation_at
        )
        if refresh_due or not cached.get("candidates"):
            candidates = await self._build_ranked_candidates()
            cached["candidates"] = candidates
            cached["refreshed_at"] = now.isoformat()
        else:
            candidates = list(cached.get("candidates") or [])
        if rotation_due:
            cached.update(self._build_rotation_payload(candidates=candidates, now=now))
        return self._persist_state(cached, now=now)

    async def active_symbols(self, *, force_refresh: bool = False) -> list[str]:
        payload = await self.state(force_refresh=force_refresh)
        return [str(symbol).upper() for symbol in payload.get("active_symbols", []) if str(symbol).strip()]

    async def scanner_snapshot(self, *, limit: int | None = None, force_refresh: bool = False) -> dict[str, object]:
        payload = await self.state(force_refresh=force_refresh)
        ranked = list(payload.get("candidates") or [])
        target = max(1, min(int(limit or self.settings.scanner_candidate_limit), len(ranked) or 1))
        return {
            "candidates": ranked[:target],
            "active_symbols": list(payload.get("active_symbols") or []),
            "fixed_symbols": list(payload.get("fixed_symbols") or []),
            "rotating_symbols": list(payload.get("rotating_symbols") or []),
            "rotation_started_at": payload.get("rotation_started_at"),
            "next_rotation_at": payload.get("next_rotation_at"),
            "seconds_until_rotation": int(payload.get("seconds_until_rotation", 0) or 0),
            "scan_universe_size": int(payload.get("scan_universe_size", len(ranked)) or len(ranked)),
            "active_limit": int(payload.get("active_limit", self.settings.scanner_active_symbol_limit) or self.settings.scanner_active_symbol_limit),
        }

    async def _build_ranked_candidates(self) -> list[dict[str, object]]:
        rows = await self.market_data.fetch_market_tickers(
            quote_asset=self.settings.default_quote_asset,
            limit=max(self.settings.scanner_candidate_limit * 3, self.settings.scanner_candidate_limit),
        )
        filtered = [row for row in rows if self._is_eligible_symbol(row)]
        top = filtered[: self.settings.scanner_candidate_limit]
        if not top:
            top = self._fallback_candidates()
        baseline_volume = median(
            [float(item.get("quote_volume", 0.0) or 0.0) for item in top if float(item.get("quote_volume", 0.0) or 0.0) > 0]
        ) if top else 0.0
        ranked: list[dict[str, object]] = []
        for item in top:
            quote_volume = float(item.get("quote_volume", 0.0) or 0.0)
            change_pct = float(item.get("change_pct", 0.0) or 0.0)
            volume_ratio = quote_volume / max(float(baseline_volume or 1.0), 1.0)
            volatility_pct = abs(change_pct)
            volume_spike_pct = max(0.0, (volume_ratio - 1.0) * 100.0)
            potential_score = min(
                100.0,
                (
                    min(volatility_pct / 8.0, 1.0) * 45.0
                    + min(max(volume_ratio - 1.0, 0.0) / 1.5, 1.0) * 35.0
                    + min(quote_volume / max(self.settings.scanner_min_quote_volume * 8.0, 1.0), 1.0) * 20.0
                ),
            )
            ranked.append(
                {
                    "symbol": str(item.get("symbol", "")).upper(),
                    "price": round(float(item.get("price", 0.0) or 0.0), 8),
                    "change_pct": round(change_pct, 4),
                    "quote_volume": round(quote_volume, 4),
                    "volume_ratio": round(volume_ratio, 4),
                    "volume_spike_pct": round(volume_spike_pct, 4),
                    "volatility_pct": round(volatility_pct, 4),
                    "potential_score": round(potential_score, 4),
                    "exchange": str(item.get("exchange", self.settings.primary_exchange)),
                }
            )
        ranked.sort(
            key=lambda entry: (
                -float(entry.get("potential_score", 0.0) or 0.0),
                -float(entry.get("quote_volume", 0.0) or 0.0),
            )
        )
        return ranked

    def _build_rotation_payload(self, *, candidates: list[dict[str, object]], now: datetime) -> dict[str, object]:
        fixed_symbols = self._normalized_symbols(self.settings.scanner_fixed_symbols)
        active_limit = max(len(fixed_symbols), int(self.settings.scanner_active_symbol_limit))
        rotating_limit = max(0, active_limit - len(fixed_symbols))
        rotating_symbols = [
            str(item.get("symbol", "")).upper()
            for item in candidates
            if str(item.get("symbol", "")).upper() not in fixed_symbols
        ][:rotating_limit]
        active_symbols = list(dict.fromkeys([*fixed_symbols, *rotating_symbols]))
        next_rotation_at = now + timedelta(hours=max(1, int(self.settings.scanner_rotation_hours)))
        return {
            "fixed_symbols": fixed_symbols,
            "rotating_symbols": rotating_symbols,
            "active_symbols": active_symbols,
            "rotation_started_at": now.isoformat(),
            "next_rotation_at": next_rotation_at.isoformat(),
            "active_limit": active_limit,
            "scan_universe_size": len(candidates),
        }

    def _persist_state(self, payload: dict[str, object], *, now: datetime) -> dict[str, object]:
        next_rotation_at = self._parse_datetime(payload.get("next_rotation_at"))
        seconds_until_rotation = 0
        if next_rotation_at is not None:
            seconds_until_rotation = max(0, int((next_rotation_at - now).total_seconds()))
        payload["seconds_until_rotation"] = seconds_until_rotation
        ttl = max(
            self.settings.scanner_refresh_minutes * 60,
            self.settings.scanner_rotation_hours * 3600,
        )
        self.cache.set_json(self.state_cache_key, payload, ttl=ttl)
        return payload

    def _is_eligible_symbol(self, row: dict[str, object]) -> bool:
        symbol = str(row.get("symbol", "")).upper().strip()
        quote = str(row.get("quote", "")).upper().strip()
        if not symbol or quote != self.settings.default_quote_asset:
            return False
        if float(row.get("quote_volume", 0.0) or 0.0) < float(self.settings.scanner_min_quote_volume):
            return False
        blocked_suffixes = ("UPUSDT", "DOWNUSDT", "BULLUSDT", "BEARUSDT")
        if symbol.endswith(blocked_suffixes):
            return False
        blocked_prefixes = ("USDC", "FDUSD", "TUSD", "BUSD")
        base = str(row.get("base", "")).upper().strip()
        if base in blocked_prefixes:
            return False
        return True

    def _fallback_candidates(self) -> list[dict[str, object]]:
        fallback: list[dict[str, object]] = []
        for symbol in self._normalized_symbols(self.settings.market_universe_symbols):
            fallback.append(
                {
                    "symbol": symbol,
                    "price": 0.0,
                    "change_pct": 0.0,
                    "quote_volume": float(self.settings.scanner_min_quote_volume),
                    "volume_ratio": 1.0,
                    "volume_spike_pct": 0.0,
                    "volatility_pct": 0.0,
                    "potential_score": 0.0,
                    "exchange": "fallback",
                }
            )
        return fallback[: self.settings.scanner_candidate_limit]

    def _normalized_symbols(self, symbols: list[str]) -> list[str]:
        return [str(symbol).upper().strip() for symbol in symbols if str(symbol).strip()]

    def _parse_datetime(self, value: object) -> datetime | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
