from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.core.config import Settings

if TYPE_CHECKING:
    from app.services.analytics_service import AnalyticsService
    from app.services.redis_cache import RedisCache


@dataclass
class StrategyController:
    settings: Settings
    analytics: AnalyticsService
    cache: RedisCache

    def adjust_weights(self, user_id: str = "system") -> dict:
        current = self.current_config(user_id)
        if self._stability_lock_active(user_id):
            current["stability_lock"] = True
            return current
        if self._cooldown_active(current.get("updated_at")):
            current["cooldown_active"] = True
            return current
        feedback = self.analytics.get_feedback(user_id)
        regime = self.current_regime(user_id)

        if float(feedback.get("volume_spike_losses", 0.0) or 0.0) > 0.6:
            current["confluence_weight_volume"] *= 0.8

        if float(feedback.get("early_exit_missed_profit", 0.0) or 0.0) > 0.5:
            current["trailing_aggressiveness"] *= 0.9

        if float(feedback.get("structure_success", 0.0) or 0.0) > 0.7:
            current["confluence_weight_structure"] *= 1.1

        current["capital_allocation_multiplier"] = 1.0
        current["stop_loss_multiplier"] = 1.0
        current["trade_frequency_multiplier"] = 1.0

        if regime == "TRENDING":
            current["trailing_aggressiveness"] *= 0.8
            current["capital_allocation_multiplier"] *= float(self.settings.regime_trending_allocation_multiplier)

        if regime == "RANGING":
            current["confluence_weight_structure"] *= float(self.settings.regime_ranging_structure_penalty)
            current["trailing_aggressiveness"] *= 0.9

        if regime == "HIGH_VOL":
            current["capital_allocation_multiplier"] *= float(self.settings.regime_high_vol_allocation_multiplier)
            current["stop_loss_multiplier"] *= 1.15
            current["trailing_aggressiveness"] *= 1.1

        if regime == "LOW_VOL":
            current["trade_frequency_multiplier"] *= float(self.settings.regime_low_vol_trade_frequency_multiplier)
            current["capital_allocation_multiplier"] *= 0.9

        current["confluence_weight_structure"] = self._bounded_weight(current["confluence_weight_structure"])
        current["confluence_weight_momentum"] = self._bounded_weight(current["confluence_weight_momentum"])
        current["confluence_weight_volume"] = self._bounded_weight(current["confluence_weight_volume"])
        current["trailing_aggressiveness"] = self._bounded_trailing(current["trailing_aggressiveness"])
        current["symbol_priorities"] = self._symbol_priorities(feedback.get("symbol_performance", {}))
        current["symbol_allocations"] = self._symbol_allocations(feedback.get("symbol_performance", {}))
        current["best_symbols"] = list(feedback.get("best_symbols", []))
        current["current_regime"] = regime
        current["cooldown_active"] = False
        current["stability_lock"] = False
        current["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.cache.set_json(
            self._config_key(user_id),
            current,
            ttl=self.settings.monitor_state_ttl_seconds,
        )
        return current

    def current_config(self, user_id: str = "system") -> dict:
        cached = self.cache.get_json(self._config_key(user_id))
        if cached:
            return {
                "confluence_weight_structure": float(cached.get("confluence_weight_structure", self.settings.confluence_weight_structure)),
                "confluence_weight_momentum": float(cached.get("confluence_weight_momentum", self.settings.confluence_weight_momentum)),
                "confluence_weight_volume": float(cached.get("confluence_weight_volume", self.settings.confluence_weight_volume)),
                "trailing_aggressiveness": float(cached.get("trailing_aggressiveness", self.settings.trailing_aggressiveness)),
                "symbol_priorities": dict(cached.get("symbol_priorities", {})),
                "symbol_allocations": dict(cached.get("symbol_allocations", {})),
                "capital_allocation_multiplier": float(cached.get("capital_allocation_multiplier", 1.0)),
                "stop_loss_multiplier": float(cached.get("stop_loss_multiplier", 1.0)),
                "trade_frequency_multiplier": float(cached.get("trade_frequency_multiplier", 1.0)),
                "best_symbols": list(cached.get("best_symbols", [])),
                "current_regime": str(cached.get("current_regime", "RANGING") or "RANGING"),
                "cooldown_active": bool(cached.get("cooldown_active", False)),
                "stability_lock": bool(cached.get("stability_lock", False)),
                "updated_at": cached.get("updated_at"),
            }
        return {
            "confluence_weight_structure": float(self.settings.confluence_weight_structure),
            "confluence_weight_momentum": float(self.settings.confluence_weight_momentum),
            "confluence_weight_volume": float(self.settings.confluence_weight_volume),
            "trailing_aggressiveness": float(self.settings.trailing_aggressiveness),
            "symbol_priorities": {},
            "symbol_allocations": {},
            "capital_allocation_multiplier": 1.0,
            "stop_loss_multiplier": 1.0,
            "trade_frequency_multiplier": 1.0,
            "best_symbols": [],
            "current_regime": "RANGING",
            "cooldown_active": False,
            "stability_lock": False,
            "updated_at": None,
        }

    def symbol_priority(self, symbol: str, user_id: str = "system") -> float:
        normalized = str(symbol or "").upper().strip()
        current = self.current_config(user_id)
        return float(current.get("symbol_priorities", {}).get(normalized, 1.0) or 1.0)

    def symbol_allocation(self, symbol: str, user_id: str = "system") -> float:
        normalized = str(symbol or "").upper().strip()
        current = self.current_config(user_id)
        return float(current.get("symbol_allocations", {}).get(normalized, 1.0) or 1.0)

    def current_regime(self, user_id: str = "system") -> str:
        payload = self.cache.get_json(self._regime_key(user_id)) or {}
        return str(payload.get("regime", "RANGING") or "RANGING").upper()

    def record_regime(self, regime: str, confidence: float, user_id: str = "system") -> None:
        self.cache.set_json(
            self._regime_key(user_id),
            {
                "regime": str(regime or "RANGING").upper(),
                "confidence": float(confidence or 0.0),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            ttl=self.settings.monitor_state_ttl_seconds,
        )

    def _symbol_priorities(self, symbol_performance: dict[str, dict]) -> dict[str, float]:
        priorities: dict[str, float] = {}
        min_trades = max(int(self.settings.symbol_priority_min_trades), 1)
        for symbol, metrics in symbol_performance.items():
            trades = int(metrics.get("trades", 0) or 0)
            if trades < min_trades:
                continue
            win_rate = float(metrics.get("win_rate", 0.0) or 0.0)
            multiplier = 1.0
            if win_rate < float(self.settings.symbol_priority_bad_win_rate):
                multiplier -= float(self.settings.symbol_priority_step)
            elif win_rate > float(self.settings.symbol_priority_good_win_rate):
                multiplier += float(self.settings.symbol_priority_step)
            priorities[str(symbol).upper()] = self._bounded_symbol_priority(multiplier)
        return priorities

    def _symbol_allocations(self, symbol_performance: dict[str, dict]) -> dict[str, float]:
        allocations: dict[str, float] = {}
        min_trades = max(int(self.settings.symbol_priority_min_trades), 1)
        for symbol, metrics in symbol_performance.items():
            trades = int(metrics.get("trades", 0) or 0)
            if trades < min_trades:
                continue
            win_rate = float(metrics.get("win_rate", 0.0) or 0.0)
            multiplier = 1.0
            if win_rate > 0.6:
                multiplier *= float(self.settings.symbol_priority_allocation_boost)
            elif win_rate < float(self.settings.symbol_priority_bad_win_rate):
                multiplier *= 0.9
            allocations[str(symbol).upper()] = self._bounded_symbol_priority(multiplier)
        return allocations

    def _bounded_weight(self, value: float) -> float:
        return min(
            max(float(value), float(self.settings.confluence_weight_min_bound)),
            float(self.settings.confluence_weight_max_bound),
        )

    def _bounded_trailing(self, value: float) -> float:
        return min(max(float(value), 0.5), 1.5)

    def _bounded_symbol_priority(self, value: float) -> float:
        return min(
            max(float(value), float(self.settings.symbol_priority_min_multiplier)),
            float(self.settings.symbol_priority_max_multiplier),
        )

    def _config_key(self, user_id: str) -> str:
        return f"strategy:adaptive_config:{user_id}"

    def _regime_key(self, user_id: str) -> str:
        return f"market:regime:{user_id}"

    def _cooldown_active(self, updated_at: str | None) -> bool:
        if not updated_at:
            return False
        try:
            last = datetime.fromisoformat(updated_at)
        except ValueError:
            return False
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - last.astimezone(timezone.utc)).total_seconds()
        return elapsed < float(self.settings.strategy_adaptation_cooldown_seconds)

    def _stability_lock_active(self, user_id: str) -> bool:
        trades = self.analytics.trade_history(
            user_id,
            limit=max(int(self.settings.strategy_stability_lock_lookback_trades), 1),
        )
        closed = [trade for trade in trades if str(trade.get("status", "CLOSED")).upper() == "CLOSED"]
        lookback = max(int(self.settings.strategy_stability_lock_lookback_trades), 1)
        if len(closed) < lookback:
            return False
        recent = closed[-lookback:]
        return all(float(trade.get("profit_pct", 0.0) or 0.0) > 0.0 for trade in recent)
