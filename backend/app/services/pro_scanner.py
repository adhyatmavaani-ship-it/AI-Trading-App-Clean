from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from typing import TYPE_CHECKING, Any

import httpx
import pandas as pd

from app.services.alerting import AlertingService
from app.services.market_data import MarketDataService
from app.services.scanner_service import ScannerService

if TYPE_CHECKING:
    from db.database import SQLiteTradeDatabase


@dataclass
class ProScannerService:
    market_data: MarketDataService
    scanner_service: ScannerService | None = None
    alerting_service: AlertingService | None = None
    store: "SQLiteTradeDatabase | None" = None

    async def run(
        self,
        *,
        user_id: str,
        symbols: list[str] | None,
        timeframe: str,
        criteria: list[dict[str, Any]],
        webhook_url: str | None = None,
        limit: int = 30,
    ) -> dict[str, Any]:
        normalized_timeframe = _normalize_timeframe(timeframe)
        target_symbols = await self._symbols(symbols=symbols, limit=limit)
        rule_id = _rule_id(user_id=user_id, timeframe=normalized_timeframe, criteria=criteria)
        rows = await asyncio.gather(
            *(self._evaluate_symbol(symbol, normalized_timeframe, criteria) for symbol in target_symbols),
            return_exceptions=True,
        )
        matches = [row for row in rows if isinstance(row, dict) and row.get("matched")]
        event = {
            "rule_id": rule_id,
            "user_id": user_id,
            "timeframe": normalized_timeframe,
            "criteria": criteria,
            "match_count": len(matches),
            "matches": matches,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        if self.store is not None:
            self.store.save_pro_scanner_rule(
                rule_id=rule_id,
                user_id=user_id,
                rule_name=_rule_name(criteria),
                timeframe=normalized_timeframe,
                symbols=target_symbols,
                criteria=criteria,
                webhook_url=webhook_url,
                match_count=len(matches),
            )
        if matches:
            await self._emit_alert(event, webhook_url=webhook_url)
        return {
            **event,
            "notification_event": {
                "enabled": bool(matches),
                "channel": "push_and_webhook" if webhook_url else "push",
                "title": "Pro scanner match" if matches else "No scanner match",
            },
        }

    async def _symbols(self, *, symbols: list[str] | None, limit: int) -> list[str]:
        explicit = [_normalize_symbol(symbol) for symbol in symbols or [] if str(symbol or "").strip()]
        if explicit:
            return list(dict.fromkeys(explicit))[:limit]
        if self.scanner_service is not None:
            snapshot = await self.scanner_service.scanner_snapshot(limit=limit)
            ranked = [str(item.get("symbol", "")).upper() for item in snapshot.get("candidates", [])]
            if ranked:
                return ranked[:limit]
        return ["BTCUSDT", "ETHUSDT", "SOLUSDT"][:limit]

    async def _evaluate_symbol(
        self,
        symbol: str,
        timeframe: str,
        criteria: list[dict[str, Any]],
    ) -> dict[str, Any]:
        frames = await self.market_data.fetch_multi_timeframe_ohlcv(symbol, intervals=(timeframe,))
        frame = _prepare_frame(frames.get(timeframe))
        if frame.empty:
            return {"symbol": symbol, "matched": False, "reason": "missing_market_data"}
        metrics = _metrics(frame)
        checks = [_criterion_result(metric=metrics, criterion=criterion) for criterion in criteria]
        matched = all(item["passed"] for item in checks) if checks else False
        score = sum(1 for item in checks if item["passed"]) / max(len(checks), 1) * 100.0
        return {
            "symbol": symbol,
            "matched": matched,
            "score": round(score, 2),
            "metrics": metrics,
            "checks": checks,
        }

    async def _emit_alert(self, event: dict[str, Any], *, webhook_url: str | None) -> None:
        title = "Pro scanner match"
        message = f"{event['match_count']} assets matched custom criteria on {event['timeframe']}."
        if self.alerting_service is not None:
            await self.alerting_service.send(title, message, severity="INFO")
        if webhook_url:
            async with httpx.AsyncClient(timeout=8) as client:
                await client.post(webhook_url, json=event)


def _normalize_symbol(symbol: str) -> str:
    normalized = str(symbol or "").upper().replace("/", "").replace("-", "").strip()
    if normalized in {"BTC", "ETH", "SOL", "BNB", "XRP"}:
        return f"{normalized}USDT"
    return normalized or "BTCUSDT"


def _normalize_timeframe(timeframe: str) -> str:
    normalized = str(timeframe or "1h").lower().strip()
    return normalized if normalized in {"1m", "3m", "5m", "15m", "1h", "4h", "1d"} else "1h"


def _rule_id(*, user_id: str, timeframe: str, criteria: list[dict[str, Any]]) -> str:
    serialized = "|".join(
        f"{item.get('field')}:{item.get('operator')}:{item.get('value')}"
        for item in criteria
    )
    digest = hashlib.sha1(f"{user_id}:{timeframe}:{serialized}".encode("utf-8")).hexdigest()[:12]
    return f"scan_{digest}"


def _rule_name(criteria: list[dict[str, Any]]) -> str:
    if not criteria:
        return "Custom Pro Scanner"
    labels = [
        f"{item.get('field')} {item.get('operator', 'above')} {item.get('value')}"
        for item in criteria[:3]
    ]
    return " AND ".join(labels)[:120]


def _prepare_frame(frame: pd.DataFrame | None) -> pd.DataFrame:
    if frame is None or getattr(frame, "empty", True):
        return pd.DataFrame()
    working = frame.copy()
    for column in ("open", "high", "low", "close", "volume"):
        if column not in working:
            return pd.DataFrame()
        working[column] = working[column].astype(float)
    return working.reset_index(drop=True)


def _metrics(frame: pd.DataFrame) -> dict[str, Any]:
    closes = frame["close"].astype(float)
    volumes = frame["volume"].astype(float)
    latest = float(closes.iloc[-1])
    previous = float(closes.iloc[-2]) if len(closes) >= 2 else latest
    avg_volume = float(volumes.tail(min(len(volumes), 20)).mean() or 0.0)
    macd = _macd(closes)
    return {
        "price": round(latest, 8),
        "change_pct": round(((latest / max(previous, 1e-8)) - 1.0) * 100.0, 4),
        "rsi": round(_rsi(closes, 14), 4),
        "volume_ratio": round(float(volumes.iloc[-1] or 0.0) / max(avg_volume, 1e-8), 4),
        "macd_crossover": macd["crossover"],
        "macd_histogram": round(macd["histogram"], 8),
    }


def _criterion_result(*, metric: dict[str, Any], criterion: dict[str, Any]) -> dict[str, Any]:
    field = str(criterion.get("field", "")).lower().strip()
    operator = str(criterion.get("operator", criterion.get("op", "above"))).lower().strip()
    expected = criterion.get("value")
    actual = metric.get(field)
    passed = False
    if field == "macd_crossover":
        passed = str(actual).lower() == str(expected or "bullish").lower()
    elif isinstance(actual, (int, float)):
        target = float(expected or 0.0)
        if operator in {"below", "lt", "<"}:
            passed = float(actual) < target
        elif operator in {"below_or_equal", "lte", "<="}:
            passed = float(actual) <= target
        elif operator in {"above_or_equal", "gte", ">="}:
            passed = float(actual) >= target
        else:
            passed = float(actual) > target
    return {
        "field": field,
        "operator": operator,
        "value": expected,
        "actual": actual,
        "passed": passed,
    }


def _rsi(closes: pd.Series, period: int) -> float:
    if len(closes) <= period:
        return 50.0
    delta = closes.diff().dropna().tail(period)
    gains = delta.clip(lower=0).mean()
    losses = delta.clip(upper=0).abs().mean()
    if losses <= 0:
        return 100.0
    rs = gains / losses
    return float(100 - (100 / (1 + rs)))


def _macd(closes: pd.Series) -> dict[str, Any]:
    ema12 = closes.ewm(span=12, adjust=False).mean()
    ema26 = closes.ewm(span=26, adjust=False).mean()
    line = ema12 - ema26
    signal = line.ewm(span=9, adjust=False).mean()
    current = float(line.iloc[-1])
    current_signal = float(signal.iloc[-1])
    previous = float(line.iloc[-2]) if len(line) >= 2 else current
    previous_signal = float(signal.iloc[-2]) if len(signal) >= 2 else current_signal
    crossover = "none"
    if previous <= previous_signal and current > current_signal:
        crossover = "bullish"
    elif previous >= previous_signal and current < current_signal:
        crossover = "bearish"
    return {"histogram": current - current_signal, "crossover": crossover}
