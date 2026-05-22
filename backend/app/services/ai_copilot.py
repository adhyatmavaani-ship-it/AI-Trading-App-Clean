from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from typing import TYPE_CHECKING, Any

import pandas as pd

from app.services.chart_intelligence import build_chart_intelligence, resample_ohlcv
from app.services.market_data import MarketDataService

if TYPE_CHECKING:
    from db.database import SQLiteTradeDatabase


@dataclass
class AICopilotService:
    market_data: MarketDataService
    store: "SQLiteTradeDatabase | None" = None

    async def answer(
        self,
        *,
        user_id: str,
        prompt: str,
        symbol: str = "BTCUSDT",
        timeframe: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        normalized_symbol = _normalize_symbol(symbol)
        normalized_timeframe = _detect_timeframe(prompt, timeframe)
        normalized_session_id = _session_id(
            user_id=user_id,
            symbol=normalized_symbol,
            timeframe=normalized_timeframe,
            explicit=session_id,
        )
        self._append_history(
            user_id=user_id,
            session_id=normalized_session_id,
            role="user",
            message=prompt,
            grounded_ticker=normalized_symbol,
            metadata={"timeframe": normalized_timeframe},
        )
        frame = await self._fetch_frame(normalized_symbol, normalized_timeframe)
        if frame.empty:
            payload = {
                "user_id": user_id,
                "session_id": normalized_session_id,
                "symbol": normalized_symbol,
                "timeframe": normalized_timeframe,
                "answer": "Market data is not available for this symbol right now.",
                "facts": {},
                "confidence": 0.0,
                "data_source": "market_data_unavailable",
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
            self._append_history(
                user_id=user_id,
                session_id=normalized_session_id,
                role="assistant",
                message=str(payload["answer"]),
                grounded_ticker=normalized_symbol,
                metadata={"confidence": 0.0, "data_source": payload["data_source"]},
            )
            return payload

        prepared = _prepare_frame(frame)
        closes = prepared["close"].astype(float)
        highs = prepared["high"].astype(float)
        lows = prepared["low"].astype(float)
        volumes = prepared["volume"].astype(float)
        latest_price = float(closes.iloc[-1])
        support = float(lows.tail(min(len(lows), 36)).quantile(0.2))
        resistance = float(highs.tail(min(len(highs), 36)).quantile(0.8))
        macd = _macd_snapshot(closes)
        volume_avg = float(volumes.tail(min(len(volumes), 20)).mean() or 0.0)
        volume_ratio = float(volumes.iloc[-1] or 0.0) / max(volume_avg, 1e-8)
        intelligence = build_chart_intelligence(
            symbol=normalized_symbol,
            interval=normalized_timeframe,
            frame=prepared,
            assistant_mode="ASSISTED",
            learning_enabled=True,
        )
        facts = {
            "latest_price": round(latest_price, 8),
            "support": round(support, 8),
            "resistance": round(resistance, 8),
            "macd_line": round(float(macd["line"]), 8),
            "macd_signal": round(float(macd["signal"]), 8),
            "macd_histogram": round(float(macd["histogram"]), 8),
            "macd_crossover": macd["crossover"],
            "volume_ratio": round(volume_ratio, 4),
            "regime": intelligence.get("regime_classifier", {}),
            "ai_why_card": intelligence.get("ai_why_card", {}),
        }
        answer = _compose_answer(
            symbol=normalized_symbol,
            timeframe=normalized_timeframe,
            prompt=prompt,
            facts=facts,
        )
        confidence = float(
            (intelligence.get("opportunity") or {}).get(
                "confidence",
                (intelligence.get("ai_why_card") or {}).get("confidence", 0.0),
            )
            or 0.0
        )
        payload = {
            "user_id": user_id,
            "session_id": normalized_session_id,
            "symbol": normalized_symbol,
            "timeframe": normalized_timeframe,
            "answer": answer,
            "facts": facts,
            "confidence": round(max(0.0, min(confidence, 100.0)), 2),
            "data_source": "live_market_data",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._append_history(
            user_id=user_id,
            session_id=normalized_session_id,
            role="assistant",
            message=answer,
            grounded_ticker=normalized_symbol,
            metadata={
                "confidence": payload["confidence"],
                "timeframe": normalized_timeframe,
                "facts": facts,
            },
        )
        return payload

    async def _fetch_frame(self, symbol: str, timeframe: str) -> pd.DataFrame:
        if timeframe == "3m":
            frames = await self.market_data.fetch_multi_timeframe_ohlcv(symbol, intervals=("1m",))
            return resample_ohlcv(frames.get("1m"), minutes=3)
        frames = await self.market_data.fetch_multi_timeframe_ohlcv(symbol, intervals=(timeframe,))
        return _prepare_frame(frames.get(timeframe))

    def _append_history(
        self,
        *,
        user_id: str,
        session_id: str,
        role: str,
        message: str,
        grounded_ticker: str,
        metadata: dict[str, Any],
    ) -> None:
        if self.store is None:
            return
        self.store.append_ai_copilot_history(
            user_id=user_id,
            session_id=session_id,
            role=role,
            message=message,
            grounded_ticker=grounded_ticker,
            metadata=metadata,
        )


def _normalize_symbol(symbol: str) -> str:
    normalized = str(symbol or "BTCUSDT").upper().replace("/", "").replace("-", "").strip()
    if not normalized:
        return "BTCUSDT"
    if normalized.endswith("USD") and not normalized.endswith("USDT"):
        return f"{normalized}T"
    if normalized in {"BTC", "ETH", "SOL", "BNB", "XRP"}:
        return f"{normalized}USDT"
    return normalized


def _detect_timeframe(prompt: str, explicit: str | None) -> str:
    candidate = str(explicit or "").strip().lower()
    text = str(prompt or "").lower()
    if not candidate:
        for value in ("1m", "3m", "5m", "15m", "1h", "4h", "1d"):
            if value in text or value.replace("h", " hour") in text:
                candidate = value
                break
    if candidate in {"4hr", "4hour", "4hours"}:
        candidate = "4h"
    if candidate in {"1hr", "1hour"}:
        candidate = "1h"
    return candidate if candidate in {"1m", "3m", "5m", "15m", "1h", "4h", "1d"} else "1h"


def _session_id(*, user_id: str, symbol: str, timeframe: str, explicit: str | None) -> str:
    normalized = str(explicit or "").strip()
    if normalized:
        return normalized[:80]
    today = datetime.now(timezone.utc).date().isoformat()
    digest = hashlib.sha1(f"{user_id}:{symbol}:{timeframe}:{today}".encode("utf-8")).hexdigest()[:12]
    return f"copilot_{digest}"


def _prepare_frame(frame: pd.DataFrame | None) -> pd.DataFrame:
    if frame is None or getattr(frame, "empty", True):
        return pd.DataFrame()
    working = frame.copy()
    for column in ("open", "high", "low", "close", "volume"):
        if column not in working:
            return pd.DataFrame()
        working[column] = working[column].astype(float)
    if "close_time" not in working and "open_time" in working:
        working["close_time"] = working["open_time"]
    return working.reset_index(drop=True)


def _macd_snapshot(closes: pd.Series) -> dict[str, Any]:
    ema12 = closes.ewm(span=12, adjust=False).mean()
    ema26 = closes.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9, adjust=False).mean()
    line = float(macd_line.iloc[-1])
    prev_line = float(macd_line.iloc[-2]) if len(macd_line) >= 2 else line
    signal_now = float(signal.iloc[-1])
    signal_prev = float(signal.iloc[-2]) if len(signal) >= 2 else signal_now
    if prev_line <= signal_prev and line > signal_now:
        crossover = "bullish"
    elif prev_line >= signal_prev and line < signal_now:
        crossover = "bearish"
    else:
        crossover = "none"
    return {
        "line": line,
        "signal": signal_now,
        "histogram": line - signal_now,
        "crossover": crossover,
    }


def _compose_answer(*, symbol: str, timeframe: str, prompt: str, facts: dict[str, Any]) -> str:
    text = str(prompt or "").lower()
    parts: list[str] = []
    if "support" in text or "resistance" in text:
        parts.append(
            f"{symbol} support is near {facts['support']}, with resistance near {facts['resistance']} on {timeframe}."
        )
    if "macd" in text or "crossover" in text:
        crossover = str(facts.get("macd_crossover", "none"))
        parts.append(
            f"MACD crossover status is {crossover}; histogram is {facts['macd_histogram']}."
        )
    if "volume" in text:
        parts.append(f"Current volume is {facts['volume_ratio']}x of the 20-period average.")
    if not parts:
        why = facts.get("ai_why_card") or {}
        headline = str(why.get("headline") or f"{symbol} is being evaluated on {timeframe}.")
        parts.append(headline)
        parts.append(
            f"Price is {facts['latest_price']}; support {facts['support']}; resistance {facts['resistance']}."
        )
    return " ".join(parts)
