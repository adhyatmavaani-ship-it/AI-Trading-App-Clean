from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from app.core.config import Settings


ATR_BUCKETS: list[tuple[str, float, float]] = [
    ("atr_vlow", 0.0, 0.0025),
    ("atr_low", 0.0025, 0.0075),
    ("atr_mid", 0.0075, 0.0150),
    ("atr_high", 0.0150, float("inf")),
]

RSI_BUCKETS: list[tuple[str, float, float]] = [
    ("rsi_vlow", float("-inf"), 35.0),
    ("rsi_low", 35.0, 45.0),
    ("rsi_mid", 45.0, 55.0),
    ("rsi_high", 55.0, 65.0),
    ("rsi_vhigh", 65.0, float("inf")),
]

GAP_BUCKETS: list[tuple[str, float, float]] = [
    ("gap_vlow", 0.0, 0.0010),
    ("gap_low", 0.0010, 0.0030),
    ("gap_mid", 0.0030, 0.0080),
    ("gap_high", 0.0080, float("inf")),
]

REGIMES = ("TRENDING", "RANGING", "VOLATILE")


def _bucket(value: float, buckets: list[tuple[str, float, float]]) -> str:
    for label, lower, upper in buckets:
        if value >= lower and value < upper:
            return label
    return buckets[-1][0]


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _default_regime_memory() -> dict[str, dict[str, Any]]:
    return {
        regime: {
            "pattern_stats": {},
            "blacklist_patterns": [],
            "whitelist_patterns": [],
            "side_stats": {
                "BUY": {"wins": 0, "losses": 0},
                "SELL": {"wins": 0, "losses": 0},
            },
            "preferred_min_atr_pct": 0.005,
            "preferred_min_trend_gap": 0.001,
            "updated_at": None,
        }
        for regime in REGIMES
    }


@dataclass(frozen=True)
class LearningSignalFeedback:
    pattern_key: str
    regime: str
    confidence_multiplier: float
    score_delta: float
    block_trade: bool
    reason: str
    trades: int
    win_rate: float

    def feature_payload(self) -> dict[str, Any]:
        return {
            "learning_pattern_key": self.pattern_key,
            "learning_regime": self.regime,
            "learning_confidence_multiplier": self.confidence_multiplier,
            "learning_score_delta": self.score_delta,
            "learning_block_trade": 1.0 if self.block_trade else 0.0,
            "learning_pattern_trades": float(self.trades),
            "learning_pattern_win_rate": self.win_rate,
            "learning_reason": self.reason,
        }


class AdaptiveLearningService:
    def __init__(self, settings: Settings, cache: Any, firestore: Any):
        self.settings = settings
        self.cache = cache
        self.firestore = firestore
        self.cache_key = "learning:adaptive_memory"
        self.snapshot_key = "learning:adaptive_snapshot"
        self.state_file = Path(self.settings.model_dir) / "adaptive_learning_state.json"
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    def evaluate_signal(
        self,
        *,
        symbol: str,
        side: str,
        strategy: str,
        feature_snapshot: dict[str, Any],
    ) -> LearningSignalFeedback:
        if not self.settings.learning_enabled or side not in {"BUY", "SELL"}:
            return LearningSignalFeedback(
                pattern_key="",
                regime=self._normalize_regime(feature_snapshot),
                confidence_multiplier=1.0,
                score_delta=0.0,
                block_trade=False,
                reason="learning_inactive",
                trades=0,
                win_rate=0.0,
            )

        state = self._load_state()
        regime = self._normalize_regime(feature_snapshot)
        pattern_key = self._pattern_key(side=side, feature_snapshot=feature_snapshot)
        regime_state = state["regime_memory"][regime]
        stats = dict(regime_state.get("pattern_stats", {}).get(pattern_key) or {})
        trades = int(stats.get("trades", 0) or 0)
        wins = int(stats.get("wins", 0) or 0)
        pnl_sum = float(stats.get("pnl_sum", 0.0) or 0.0)
        win_rate = (wins / trades) if trades else 0.0
        blacklisted = pattern_key in set(regime_state.get("blacklist_patterns", []))
        whitelisted = pattern_key in set(regime_state.get("whitelist_patterns", []))

        confidence_multiplier = 1.0
        score_delta = 0.0
        reason_parts = [f"{strategy}:{symbol}:{pattern_key}"]

        if blacklisted:
            confidence_multiplier -= float(self.settings.learning_confidence_penalty)
            score_delta -= float(self.settings.learning_score_penalty)
            reason_parts.append("blacklisted_pattern")
        elif whitelisted:
            confidence_multiplier += float(self.settings.learning_confidence_boost)
            score_delta += float(self.settings.learning_score_boost)
            reason_parts.append("whitelisted_pattern")

        if trades >= self.settings.learning_min_pattern_samples:
            centered_win_rate = (win_rate - 0.5) * 2.0
            expectancy_component = _clamp(pnl_sum / max(trades, 1), -1.5, 1.5)
            confidence_multiplier += centered_win_rate * 0.08 + expectancy_component * 0.03
            score_delta += centered_win_rate * 10.0 + expectancy_component * 4.0
            reason_parts.append(f"wr={win_rate:.2f}")

        side_stats = regime_state.get("side_stats", {}).get(side, {})
        side_total = int(side_stats.get("wins", 0) or 0) + int(side_stats.get("losses", 0) or 0)
        if side_total >= self.settings.learning_min_pattern_samples:
            side_wr = int(side_stats.get("wins", 0) or 0) / max(side_total, 1)
            confidence_multiplier += (side_wr - 0.5) * 0.06
            score_delta += (side_wr - 0.5) * 6.0
            reason_parts.append(f"side_wr={side_wr:.2f}")

        block_trade = blacklisted and trades >= self.settings.learning_min_pattern_samples
        return LearningSignalFeedback(
            pattern_key=pattern_key,
            regime=regime,
            confidence_multiplier=round(_clamp(confidence_multiplier, 0.55, 1.20), 6),
            score_delta=round(_clamp(score_delta, -25.0, 15.0), 6),
            block_trade=block_trade,
            reason="; ".join(reason_parts),
            trades=trades,
            win_rate=round(win_rate, 6),
        )

    def record_trade_outcome(self, *, trade_id: str, active_trade: dict[str, Any], pnl: float) -> dict[str, Any]:
        if not self.settings.learning_enabled:
            return {}

        feature_snapshot = dict(active_trade.get("feature_snapshot") or {})
        side = str(active_trade.get("side", "")).upper()
        regime = self._normalize_regime(feature_snapshot or active_trade)
        pattern_key = str(feature_snapshot.get("learning_pattern_key") or self._pattern_key(side=side, feature_snapshot=feature_snapshot))
        if side not in {"BUY", "SELL"} or not pattern_key:
            return {}

        state = self._load_state()
        regime_state = state["regime_memory"][regime]
        pattern_stats = regime_state.setdefault("pattern_stats", {})
        stats = dict(pattern_stats.get(pattern_key) or {})

        stats["trades"] = int(stats.get("trades", 0) or 0) + 1
        stats["wins"] = int(stats.get("wins", 0) or 0) + int(pnl > 0)
        stats["losses"] = int(stats.get("losses", 0) or 0) + int(pnl <= 0)
        stats["pnl_sum"] = round(float(stats.get("pnl_sum", 0.0) or 0.0) + float(pnl), 8)
        stats["avg_pnl"] = round(stats["pnl_sum"] / max(stats["trades"], 1), 8)
        stats["last_pnl"] = round(float(pnl), 8)
        stats["last_trade_id"] = trade_id
        stats["updated_at"] = datetime.now(timezone.utc).isoformat()
        pattern_stats[pattern_key] = stats

        side_stats = regime_state.setdefault("side_stats", {}).setdefault(side, {"wins": 0, "losses": 0})
        if pnl > 0:
            side_stats["wins"] = int(side_stats.get("wins", 0) or 0) + 1
        else:
            side_stats["losses"] = int(side_stats.get("losses", 0) or 0) + 1

        atr_pct = self._atr_pct(feature_snapshot)
        trend_gap = self._trend_gap(feature_snapshot)
        if pnl > 0:
            current_atr = float(regime_state.get("preferred_min_atr_pct", 0.005) or 0.005)
            current_gap = float(regime_state.get("preferred_min_trend_gap", 0.001) or 0.001)
            regime_state["preferred_min_atr_pct"] = round(((current_atr * 3.0) + atr_pct) / 4.0, 6)
            regime_state["preferred_min_trend_gap"] = round(((current_gap * 3.0) + trend_gap) / 4.0, 6)

        win_rate = stats["wins"] / max(stats["trades"], 1)
        is_blacklisted = (
            stats["trades"] >= self.settings.learning_min_pattern_samples
            and win_rate <= float(self.settings.learning_blacklist_win_rate_threshold)
            and stats["avg_pnl"] < 0
        )
        is_whitelisted = (
            stats["trades"] >= self.settings.learning_min_pattern_samples
            and win_rate >= float(self.settings.learning_whitelist_win_rate_threshold)
            and stats["avg_pnl"] > 0
        )
        blacklisted = set(regime_state.get("blacklist_patterns", []))
        whitelisted = set(regime_state.get("whitelist_patterns", []))
        if is_blacklisted:
            blacklisted.add(pattern_key)
            whitelisted.discard(pattern_key)
        elif is_whitelisted:
            whitelisted.add(pattern_key)
            blacklisted.discard(pattern_key)
        else:
            blacklisted.discard(pattern_key)
            whitelisted.discard(pattern_key)
        regime_state["blacklist_patterns"] = sorted(blacklisted)
        regime_state["whitelist_patterns"] = sorted(whitelisted)
        regime_state["updated_at"] = datetime.now(timezone.utc).isoformat()

        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save_state(state)
        snapshot = self.snapshot()
        self.cache.set_json(self.snapshot_key, snapshot, ttl=self.settings.monitor_state_ttl_seconds)
        self.firestore.save_performance_snapshot("learning:adaptive", snapshot)
        return {
            "pattern_key": pattern_key,
            "regime": regime,
            "trades": stats["trades"],
            "win_rate": round(win_rate, 6),
            "blacklisted": pattern_key in blacklisted,
            "whitelisted": pattern_key in whitelisted,
        }

    def snapshot(self) -> dict[str, Any]:
        state = self._load_state()
        regime_payload: dict[str, Any] = {}
        total_blacklist = 0
        total_whitelist = 0
        for regime, payload in state["regime_memory"].items():
            pattern_stats = payload.get("pattern_stats", {})
            total_blacklist += len(payload.get("blacklist_patterns", []))
            total_whitelist += len(payload.get("whitelist_patterns", []))
            regime_payload[regime] = {
                "tracked_patterns": len(pattern_stats),
                "blacklist_patterns": payload.get("blacklist_patterns", []),
                "whitelist_patterns": payload.get("whitelist_patterns", []),
                "preferred_min_atr_pct": float(payload.get("preferred_min_atr_pct", 0.0) or 0.0),
                "preferred_min_trend_gap": float(payload.get("preferred_min_trend_gap", 0.0) or 0.0),
                "updated_at": payload.get("updated_at"),
            }
        return {
            "enabled": self.settings.learning_enabled,
            "updated_at": state.get("updated_at"),
            "blacklist_total": total_blacklist,
            "whitelist_total": total_whitelist,
            "regimes": regime_payload,
        }

    def _load_state(self) -> dict[str, Any]:
        payload = self.cache.get_json(self.cache_key) or self._load_file_state()
        regime_memory = _default_regime_memory()
        loaded_regimes = payload.get("regime_memory") or {}
        for regime in REGIMES:
            if regime in loaded_regimes:
                regime_memory[regime].update(loaded_regimes[regime] or {})
        return {
            "updated_at": payload.get("updated_at"),
            "regime_memory": regime_memory,
        }

    def _save_state(self, state: dict[str, Any]) -> None:
        self.cache.set_json(self.cache_key, state, ttl=self.settings.learning_memory_ttl_seconds)
        self.state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def _load_file_state(self) -> dict[str, Any]:
        if not self.state_file.exists():
            return {}
        try:
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _pattern_key(self, *, side: str, feature_snapshot: dict[str, Any]) -> str:
        atr_pct = self._atr_pct(feature_snapshot)
        rsi = self._rsi_value(feature_snapshot)
        trend_gap = self._trend_gap(feature_snapshot)
        return (
            f"{side.lower()}|"
            f"{_bucket(atr_pct, ATR_BUCKETS)}|"
            f"{_bucket(rsi, RSI_BUCKETS)}|"
            f"{_bucket(trend_gap, GAP_BUCKETS)}"
        )

    def _normalize_regime(self, feature_snapshot: dict[str, Any]) -> str:
        regime = str(
            feature_snapshot.get("learning_regime")
            or feature_snapshot.get("regime")
            or feature_snapshot.get("regime_type")
            or "RANGING"
        ).upper()
        return regime if regime in REGIMES else "RANGING"

    def _atr_pct(self, feature_snapshot: dict[str, Any]) -> float:
        atr = float(
            feature_snapshot.get("atr")
            or feature_snapshot.get("15m_atr")
            or feature_snapshot.get("5m_atr")
            or 0.0
        )
        price = float(feature_snapshot.get("price") or feature_snapshot.get("entry") or 0.0)
        if price > 0 and atr > 0:
            return abs(atr / price)
        return abs(float(feature_snapshot.get("volatility", feature_snapshot.get("expected_risk", 0.0)) or 0.0))

    def _rsi_value(self, feature_snapshot: dict[str, Any]) -> float:
        return float(
            feature_snapshot.get("rsi")
            or feature_snapshot.get("5m_rsi")
            or feature_snapshot.get("15m_rsi")
            or 50.0
        )

    def _trend_gap(self, feature_snapshot: dict[str, Any]) -> float:
        return abs(
            float(
                feature_snapshot.get("trend_gap")
                or feature_snapshot.get("15m_ema_spread")
                or feature_snapshot.get("5m_ema_spread")
                or 0.0
            )
        )
