from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from app.services.redis_cache import RedisCache
from app.services.trade_journal_intelligence import TradeJournalIntelligence

if TYPE_CHECKING:
    from db.database import SQLiteTradeDatabase


@dataclass
class AutomatedJournalService:
    cache: RedisCache
    store: "SQLiteTradeDatabase | None" = None

    def report(self, *, user_id: str, trade: dict[str, Any]) -> dict[str, Any]:
        symbol = str(trade.get("symbol", "UNKNOWN")).upper()
        entry = float(trade.get("entry_price", trade.get("entry", 0.0)) or 0.0)
        exit_price = float(trade.get("exit_price", trade.get("exit", entry)) or entry)
        pnl = float(trade.get("pnl", trade.get("profit", exit_price - entry)) or 0.0)
        side = str(trade.get("side", "BUY")).upper()
        entry_ts = _parse_time(trade.get("entry_timestamp") or trade.get("opened_at"))
        exit_ts = _parse_time(trade.get("exit_timestamp") or trade.get("closed_at"))
        hold_minutes = max((exit_ts - entry_ts).total_seconds() / 60.0, 0.0)
        tags = _psychology_tags(trade=trade, pnl=pnl, hold_minutes=hold_minutes)
        svg = _snapshot_svg(symbol=symbol, side=side, entry=entry, exit_price=exit_price, pnl=pnl)
        generated_at = datetime.now(timezone.utc).isoformat()
        trade_id = str(trade.get("trade_id") or f"{symbol}:{entry_ts.isoformat()}:{exit_ts.isoformat()}")
        report_id = _report_id(user_id=user_id, trade_id=trade_id)
        behavioral_summary = TradeJournalIntelligence(self.cache).record(
            user_id=user_id,
            event={
                "type": "closed_trade",
                "symbol": symbol,
                "setup_quality": float(trade.get("setup_quality", 70.0) or 70.0),
                "risk_state": "RULE_VIOLATION" if "rule_violation" in tags else "PLANNED",
                "followed_plan": "rule_violation" not in tags and "fomo_entry" not in tags,
            },
        )
        report = {
            "report_id": report_id,
            "user_id": user_id,
            "symbol": symbol,
            "result": "WIN" if pnl > 0 else "LOSS" if pnl < 0 else "FLAT",
            "pnl": round(pnl, 4),
            "hold_minutes": round(hold_minutes, 2),
            "annotations": [
                {"type": "entry", "price": round(entry, 8), "timestamp": entry_ts.isoformat()},
                {"type": "exit", "price": round(exit_price, 8), "timestamp": exit_ts.isoformat()},
            ],
            "snapshot_image": {
                "mime_type": "image/svg+xml",
                "data_url": "data:image/svg+xml;base64,"
                + base64.b64encode(svg.encode("utf-8")).decode("ascii"),
            },
            "psychology_tags": tags,
            "analysis": _analysis_text(symbol=symbol, pnl=pnl, hold_minutes=hold_minutes, tags=tags),
            "behavioral_summary": behavioral_summary,
            "generated_at": generated_at,
        }
        if self.store is not None:
            self.store.save_automated_journal_report(report, trade={**trade, "trade_id": trade_id})
        return report


def _parse_time(value: object) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value or "").strip()
    if text:
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _psychology_tags(*, trade: dict[str, Any], pnl: float, hold_minutes: float) -> list[str]:
    reason = str(trade.get("reason", trade.get("ai_suggestion", ""))).lower()
    tags: list[str] = []
    if pnl > 0 and hold_minutes <= 15:
        tags.append("early_winner_exit")
    if pnl < 0 and hold_minutes >= 120:
        tags.append("late_loser_exit")
    if "wait" in reason or "overbought" in reason or "fomo" in reason:
        tags.append("fomo_entry")
    if bool(trade.get("rule_violation", False)):
        tags.append("rule_violation")
    return tags or ["plan_followed"]


def _analysis_text(*, symbol: str, pnl: float, hold_minutes: float, tags: list[str]) -> str:
    if "early_winner_exit" in tags:
        return f"{symbol} winner was closed quickly after {hold_minutes:.0f} minutes; review whether target rules were followed."
    if "late_loser_exit" in tags:
        return f"{symbol} loser stayed open for {hold_minutes:.0f} minutes; tighten stop discipline before next setup."
    if "fomo_entry" in tags:
        return f"{symbol} entry conflicts with AI wait/overbought context; tag this as FOMO before repeating the pattern."
    return f"{symbol} closed with {pnl:.2f} PnL and no major discipline warning."


def _report_id(*, user_id: str, trade_id: str) -> str:
    digest = hashlib.sha1(f"{user_id}:{trade_id}".encode("utf-8")).hexdigest()[:12]
    return f"journal_{digest}"


def _snapshot_svg(*, symbol: str, side: str, entry: float, exit_price: float, pnl: float) -> str:
    color = "#2dd4bf" if pnl >= 0 else "#fb7185"
    entry_y = 140
    exit_y = 80 if pnl >= 0 else 200
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="720" height="320" viewBox="0 0 720 320">
  <rect width="720" height="320" fill="#08111f"/>
  <text x="32" y="42" fill="#e5eefc" font-family="Arial" font-size="24" font-weight="700">{symbol} {side} Trade Journal</text>
  <line x1="70" y1="250" x2="650" y2="250" stroke="#213047" stroke-width="2"/>
  <polyline points="90,180 190,150 300,{entry_y} 420,120 560,{exit_y}" fill="none" stroke="{color}" stroke-width="5"/>
  <circle cx="300" cy="{entry_y}" r="9" fill="#38bdf8"/>
  <circle cx="560" cy="{exit_y}" r="9" fill="{color}"/>
  <text x="270" y="{entry_y - 18}" fill="#e5eefc" font-family="Arial" font-size="16">ENTRY {entry:.4f}</text>
  <text x="522" y="{exit_y - 18}" fill="#e5eefc" font-family="Arial" font-size="16">EXIT {exit_price:.4f}</text>
  <text x="32" y="292" fill="{color}" font-family="Arial" font-size="20" font-weight="700">PnL {pnl:.2f}</text>
</svg>"""
