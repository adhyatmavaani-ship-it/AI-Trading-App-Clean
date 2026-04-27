from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pandas as pd

from app.core.config import Settings
from app.services.market_data import MarketDataService
from app.services.user_experience_engine import UserExperienceEngine


@dataclass
class MarketUniverseScanner:
    settings: Settings
    market_data: MarketDataService
    user_experience_engine: UserExperienceEngine

    async def snapshot(self, limit: int | None = None) -> dict[str, object]:
        symbols = list(self.settings.market_universe_symbols or self.settings.websocket_symbols)
        if not symbols:
            symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        scan_limit = max(1, min(int(limit or self.settings.market_universe_scan_limit), len(symbols)))
        entries = await asyncio.gather(
            *(self._scan_symbol(symbol) for symbol in symbols[:scan_limit]),
            return_exceptions=True,
        )
        normalized_entries = [entry for entry in entries if isinstance(entry, dict)]
        normalized_entries.sort(
            key=lambda item: (
                -float(item.get("quote_volume", 0.0) or 0.0),
                -abs(float(item.get("change_pct", 0.0) or 0.0)),
            )
        )
        ai_pick_symbols = {
            str(item.get("symbol", "")).upper()
            for item in self.user_experience_engine.readiness(limit=scan_limit)
            if item.get("symbol")
        }
        ai_picks = [item for item in normalized_entries if str(item.get("symbol", "")).upper() in ai_pick_symbols][:6]
        if len(ai_picks) < 6:
            for item in normalized_entries:
                if item in ai_picks:
                    continue
                ai_picks.append(item)
                if len(ai_picks) >= 6:
                    break
        top_gainers = sorted(
            normalized_entries,
            key=lambda item: float(item.get("change_pct", 0.0) or 0.0),
            reverse=True,
        )[:6]
        high_volatility = sorted(
            normalized_entries,
            key=lambda item: float(item.get("volatility_pct", 0.0) or 0.0),
            reverse=True,
        )[:6]
        return {
            "count": len(normalized_entries),
            "items": normalized_entries,
            "categories": {
                "top_gainers": top_gainers,
                "high_volatility": high_volatility,
                "ai_picks": ai_picks,
            },
        }

    async def _scan_symbol(self, symbol: str) -> dict[str, object]:
        frames = await self.market_data.fetch_multi_timeframe_ohlcv(symbol, intervals=("5m", "15m"))
        latest_price = await self.market_data.fetch_latest_price(symbol)
        five_minute = frames.get("5m", pd.DataFrame())
        fifteen_minute = frames.get("15m", pd.DataFrame())
        if five_minute.empty:
            raise ValueError(f"missing 5m frame for {symbol}")
        close_series = five_minute["close"].astype(float)
        volume_series = five_minute["volume"].astype(float)
        latest_close = float(close_series.iloc[-1])
        previous_close = float(close_series.iloc[-2]) if len(close_series) > 1 else latest_close
        change_pct = ((latest_close / max(previous_close, 1e-8)) - 1.0) * 100.0
        volume_baseline = float(volume_series.tail(min(len(volume_series), 20)).mean() or 0.0)
        latest_volume = float(volume_series.iloc[-1])
        volume_ratio = latest_volume / max(volume_baseline, 1e-8) if volume_baseline > 0 else 0.0
        volatility_pct = (
            float(close_series.pct_change().dropna().tail(20).std() or 0.0) * 100.0
        )
        trend_pct = 0.0
        if not fifteen_minute.empty:
            trend_series = fifteen_minute["close"].astype(float)
            if len(trend_series) > 12:
                rolling_start = float(trend_series.iloc[-12])
                trend_pct = ((float(trend_series.iloc[-1]) / max(rolling_start, 1e-8)) - 1.0) * 100.0
        quote_volume = latest_close * latest_volume
        category = "high_volatility" if volatility_pct >= 2.0 else "top_gainer" if change_pct >= 0 else "watch"
        return {
            "symbol": str(symbol).upper(),
            "price": round(float(latest_price), 8),
            "change_pct": round(change_pct, 4),
            "volume_ratio": round(volume_ratio, 4),
            "volatility_pct": round(volatility_pct, 4),
            "trend_pct": round(trend_pct, 4),
            "quote_volume": round(quote_volume, 4),
            "category": category,
        }
