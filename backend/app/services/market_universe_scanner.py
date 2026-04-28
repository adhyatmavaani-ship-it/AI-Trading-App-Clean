from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pandas as pd

from app.core.config import Settings
from app.services.market_data import MarketDataService
from app.services.scanner_service import ScannerService
from app.services.user_experience_engine import UserExperienceEngine


@dataclass
class MarketUniverseScanner:
    settings: Settings
    market_data: MarketDataService
    user_experience_engine: UserExperienceEngine
    scanner_service: ScannerService | None = None

    async def snapshot(self, limit: int | None = None) -> dict[str, object]:
        scanner_snapshot = (
            await self.scanner_service.scanner_snapshot(limit=limit)
            if self.scanner_service is not None
            else {}
        )
        symbols = list(
            scanner_snapshot.get("active_symbols")
            or self.settings.market_universe_symbols
            or self.settings.websocket_symbols
        )
        if not symbols:
            symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        scan_limit = max(1, min(int(limit or self.settings.market_universe_scan_limit), len(symbols)))
        candidate_map = {
            str(item.get("symbol", "")).upper(): dict(item)
            for item in scanner_snapshot.get("candidates", [])
        }
        entries = await asyncio.gather(
            *(self._scan_symbol(symbol) for symbol in symbols[:scan_limit]),
            return_exceptions=True,
        )
        normalized_entries = [entry for entry in entries if isinstance(entry, dict)]
        for item in normalized_entries:
            candidate = candidate_map.get(str(item.get("symbol", "")).upper(), {})
            if candidate:
                item["potential_score"] = round(float(candidate.get("potential_score", 0.0) or 0.0), 4)
                item["scanner_quote_volume"] = round(float(candidate.get("quote_volume", 0.0) or 0.0), 4)
                item["volume_spike_pct"] = round(float(candidate.get("volume_spike_pct", 0.0) or 0.0), 4)
        normalized_entries.sort(
            key=lambda item: (
                -float(item.get("potential_score", 0.0) or 0.0),
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
            "scanner": {
                "active_symbols": list(scanner_snapshot.get("active_symbols", symbols[:scan_limit])),
                "fixed_symbols": list(scanner_snapshot.get("fixed_symbols", [])),
                "rotating_symbols": list(scanner_snapshot.get("rotating_symbols", [])),
                "rotation_started_at": scanner_snapshot.get("rotation_started_at"),
                "next_rotation_at": scanner_snapshot.get("next_rotation_at"),
                "seconds_until_rotation": int(scanner_snapshot.get("seconds_until_rotation", 0) or 0),
                "candidates": list(scanner_snapshot.get("candidates", [])),
            },
            "categories": {
                "top_gainers": top_gainers,
                "high_volatility": high_volatility,
                "ai_picks": ai_picks,
            },
        }

    async def summary(self, limit: int | None = None) -> dict[str, object]:
        snapshot = await self.snapshot(limit=limit)
        items = list(snapshot.get("items", []))
        if not items:
            return {
                "sentiment_score": 0.0,
                "sentiment_label": "NEUTRAL",
                "market_breadth": 0.0,
                "avg_change_pct": 0.0,
                "avg_volatility_pct": 0.0,
                "participation_score": 0.0,
                "confidence_score": 0.0,
                "ticker": [],
                "heatmap": [],
                "top_movers": [],
            }

        gainers = [item for item in items if float(item.get("change_pct", 0.0) or 0.0) > 0]
        decliners = [item for item in items if float(item.get("change_pct", 0.0) or 0.0) < 0]
        avg_change_pct = sum(float(item.get("change_pct", 0.0) or 0.0) for item in items) / max(len(items), 1)
        avg_volatility_pct = sum(float(item.get("volatility_pct", 0.0) or 0.0) for item in items) / max(len(items), 1)
        avg_volume_ratio = sum(float(item.get("volume_ratio", 0.0) or 0.0) for item in items) / max(len(items), 1)
        avg_trend_pct = sum(float(item.get("trend_pct", 0.0) or 0.0) for item in items) / max(len(items), 1)
        breadth = (len(gainers) - len(decliners)) / max(len(items), 1)
        participation_score = max(0.0, min(avg_volume_ratio / 2.5, 1.0))
        confidence_score = max(
            0.0,
            min(
                (
                    abs(breadth) * 0.35
                    + min(abs(avg_change_pct) / 3.0, 1.0) * 0.25
                    + participation_score * 0.25
                    + min(avg_volatility_pct / 4.0, 1.0) * 0.15
                ),
                1.0,
            ),
        )
        sentiment_score = max(
            -100.0,
            min(
                (
                    breadth * 42.0
                    + avg_change_pct * 12.0
                    + avg_trend_pct * 4.0
                    + (participation_score - 0.5) * 20.0
                ),
                100.0,
            ),
        )
        if sentiment_score >= 25:
            sentiment_label = "BULLISH"
        elif sentiment_score <= -25:
            sentiment_label = "BEARISH"
        else:
            sentiment_label = "NEUTRAL"

        ticker = [
            {
                "symbol": str(item.get("symbol", "")).upper(),
                "price": round(float(item.get("price", 0.0) or 0.0), 8),
                "change_pct": round(float(item.get("change_pct", 0.0) or 0.0), 4),
            }
            for item in sorted(
                items,
                key=lambda entry: float(entry.get("quote_volume", 0.0) or 0.0),
                reverse=True,
            )[:10]
        ]
        heatmap = [
            {
                "symbol": str(item.get("symbol", "")).upper(),
                "change_pct": round(float(item.get("change_pct", 0.0) or 0.0), 4),
                "intensity": round(
                    min(abs(float(item.get("change_pct", 0.0) or 0.0)) / 4.0, 1.0),
                    4,
                ),
            }
            for item in sorted(
                items,
                key=lambda entry: abs(float(entry.get("change_pct", 0.0) or 0.0)),
                reverse=True,
            )[:12]
        ]
        top_movers = sorted(
            items,
            key=lambda item: abs(float(item.get("change_pct", 0.0) or 0.0)),
            reverse=True,
        )[:5]
        return {
            "sentiment_score": round(sentiment_score, 4),
            "sentiment_label": sentiment_label,
            "market_breadth": round(breadth, 4),
            "avg_change_pct": round(avg_change_pct, 4),
            "avg_volatility_pct": round(avg_volatility_pct, 4),
            "participation_score": round(participation_score, 4),
            "confidence_score": round(confidence_score, 4),
            "ticker": ticker,
            "heatmap": heatmap,
            "top_movers": top_movers,
            "scanner": snapshot.get("scanner", {}),
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
