from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.core.config import Settings

if TYPE_CHECKING:
    from app.services.firestore_repo import FirestoreRepository
    from app.services.redis_state_manager import RedisStateManager
    from app.services.redis_cache import RedisCache


@dataclass
class AnalyticsService:
    settings: Settings
    cache: RedisCache
    redis_state_manager: RedisStateManager
    firestore: FirestoreRepository | None = None

    def active_trades(self, user_id: str) -> list[dict]:
        rows: list[dict] = []
        for trade in self.redis_state_manager.restore_active_trades():
            if str(trade.get("user_id", "") or "") != user_id:
                continue
            rows.append(
                {
                    "trade_id": str(trade.get("trade_id", "")),
                    "symbol": str(trade.get("symbol", "")),
                    "side": str(trade.get("side", "")),
                    "entry": float(trade.get("entry", 0.0) or 0.0),
                    "stop_loss": float(trade.get("stop_loss", 0.0) or 0.0),
                    "take_profit": float(trade.get("take_profit", 0.0) or 0.0),
                    "trailing_stop_pct": float(trade.get("trailing_stop_pct", 0.0) or 0.0),
                    "executed_quantity": float(trade.get("executed_quantity", 0.0) or 0.0),
                    "entry_reason": str(trade.get("entry_reason", "") or ""),
                    "exit_reason": str(trade.get("exit_reason", "") or ""),
                    "exit_type": str(trade.get("exit_type", "") or ""),
                    "max_profit": float(trade.get("max_profit", 0.0) or 0.0),
                    "risk_fraction": float(trade.get("risk_fraction", 0.0) or 0.0),
                    "portfolio_correlation_risk": float(trade.get("portfolio_correlation_risk", 0.0) or 0.0),
                    "regime": str(trade.get("regime", "") or ""),
                    "status": str(trade.get("status", "")),
                    "created_at": trade.get("created_at"),
                }
            )
        rows.sort(key=lambda item: str(item.get("created_at") or ""))
        return rows

    def trade_history(self, user_id: str, *, limit: int = 100) -> list[dict]:
        bucket = self.cache.get_json(self._history_key(user_id)) or {"trades": []}
        rows = list(bucket.get("trades", []))
        return rows[-max(1, limit) :]

    def record_closed_trade(
        self,
        *,
        user_id: str,
        trade_id: str,
        active_trade: dict,
        close_payload: dict,
        exit_price: float,
        exit_reason: str,
        exit_type: str,
    ) -> dict:
        entry = float(active_trade.get("entry", 0.0) or 0.0)
        side = str(active_trade.get("side", "BUY") or "BUY").upper()
        created_at = self._coerce_datetime(active_trade.get("created_at"))
        closed_at = datetime.now(timezone.utc)
        duration_sec = max(0, int((closed_at - created_at).total_seconds()))
        direction = 1.0 if side == "BUY" else -1.0
        profit_pct = 0.0
        if entry > 0:
            profit_pct = ((float(exit_price) - entry) / entry) * 100.0 * direction
        max_profit_pct = float(active_trade.get("max_profit", 0.0) or 0.0) * 100.0
        feature_snapshot = dict(active_trade.get("feature_snapshot") or {})
        entry_reason = str(active_trade.get("entry_reason", "") or "")
        regime = str(
            active_trade.get("regime")
            or feature_snapshot.get("regime")
            or feature_snapshot.get("regime_type")
            or "RANGING"
        ).upper()
        tags = self._derive_tags(
            entry_reason=entry_reason,
            exit_reason=exit_reason,
            feature_snapshot=feature_snapshot,
        )
        record = {
            "trade_id": trade_id,
            "user_id": user_id,
            "symbol": str(active_trade.get("symbol", "")),
            "side": side,
            "entry": round(entry, 8),
            "exit": round(float(exit_price), 8),
            "regime": regime,
            "profit_pct": round(profit_pct, 8),
            "realized_pnl": round(float(close_payload.get("realized_pnl", 0.0) or 0.0), 8),
            "max_profit": round(max_profit_pct, 8),
            "exit_type": exit_type,
            "entry_reason": entry_reason,
            "exit_reason": exit_reason,
            "duration_sec": duration_sec,
            "status": str(close_payload.get("status", "CLOSED")),
            "closed_at": closed_at.isoformat(),
            "created_at": created_at.isoformat(),
            "tags": tags,
        }
        history = self.cache.get_json(self._history_key(user_id)) or {"trades": []}
        trades = list(history.get("trades", []))
        trades.append(record)
        keep = max(int(self.settings.analytics_history_limit), 1)
        self.cache.set_json(
            self._history_key(user_id),
            {"trades": trades[-keep:]},
            ttl=self.settings.monitor_state_ttl_seconds,
        )
        summary = self.summary(user_id)
        performance = self.performance(user_id)
        if self.firestore is not None and hasattr(self.firestore, "save_performance_snapshot"):
            self.firestore.save_performance_snapshot(f"analytics:trade:{trade_id}", record)
            self.firestore.save_performance_snapshot(f"analytics:summary:{user_id}", summary)
            self.firestore.save_performance_snapshot(f"analytics:performance:{user_id}", performance)
        return record

    def summary(self, user_id: str) -> dict:
        trades = self.trade_history(user_id, limit=max(int(self.settings.analytics_history_limit), 1))
        closed = [trade for trade in trades if str(trade.get("status", "CLOSED")).upper() == "CLOSED"]
        if not closed:
            return {
                "user_id": user_id,
                "trades": 0,
                "win_rate": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "max_drawdown": 0.0,
                "profit_factor": 0.0,
                "expectancy": 0.0,
                "net_profit_pct": 0.0,
                "best_symbols": [],
                "best_regime": "",
                "worst_regime": "",
                "regime_win_rates": {},
                "worst_exit_reasons": [],
                "most_profitable_setup": "",
                "false_signal_rate": 0.0,
                "capital_utilization": 0.0,
                "risk_exposure": 0.0,
                "correlation_risk": 0.0,
                "regime_distribution": {},
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        profits = [float(item.get("profit_pct", 0.0) or 0.0) for item in closed]
        wins = [value for value in profits if value > 0]
        losses = [abs(value) for value in profits if value < 0]
        win_rate = len(wins) / max(len(closed), 1)
        avg_win = sum(wins) / max(len(wins), 1) if wins else 0.0
        avg_loss = sum(losses) / max(len(losses), 1) if losses else 0.0
        profit_factor = sum(wins) / max(sum(losses), 1e-8) if wins else 0.0
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
        net_profit_pct = sum(profits)
        max_drawdown = self._max_drawdown_pct(profits)
        best_symbols = self._best_symbols(closed)
        regime_win_rates = self._regime_win_rates(closed)
        best_regime, worst_regime = self._regime_edges(closed)
        worst_exit_reasons = self._worst_exit_reasons(closed)
        most_profitable_setup = self._most_profitable_setup(closed)
        false_signal_rate = self._false_signal_rate(closed)
        portfolio_metrics = self._portfolio_metrics(user_id)
        regime_distribution = self._regime_distribution(closed)
        return {
            "user_id": user_id,
            "trades": len(closed),
            "win_rate": round(win_rate, 8),
            "avg_win": round(avg_win, 8),
            "avg_loss": round(avg_loss, 8),
            "max_drawdown": round(max_drawdown, 8),
            "profit_factor": round(profit_factor, 8),
            "expectancy": round(expectancy, 8),
            "net_profit_pct": round(net_profit_pct, 8),
            "best_symbols": best_symbols,
            "best_regime": best_regime,
            "worst_regime": worst_regime,
            "regime_win_rates": regime_win_rates,
            "worst_exit_reasons": worst_exit_reasons,
            "most_profitable_setup": most_profitable_setup,
            "false_signal_rate": round(false_signal_rate, 8),
            "capital_utilization": round(float(portfolio_metrics.get("capital_utilization", 0.0) or 0.0), 8),
            "risk_exposure": round(float(portfolio_metrics.get("risk_exposure", 0.0) or 0.0), 8),
            "correlation_risk": round(float(portfolio_metrics.get("correlation_risk", 0.0) or 0.0), 8),
            "regime_distribution": regime_distribution,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def performance(self, user_id: str) -> dict:
        history = self.trade_history(user_id, limit=max(int(self.settings.analytics_history_limit), 1))
        summary = self.summary(user_id)
        adaptive = self.cache.get_json("strategy:adaptive_config:system") or {}
        exit_reason_stats = self._bucket_performance(history, key="exit_reason")
        exit_type_stats = self._bucket_performance(history, key="exit_type")
        tag_stats = self._tag_performance(history)
        insights = self._insights(history, summary, exit_reason_stats, exit_type_stats, tag_stats)
        return {
            "summary": summary,
            "weights": {
                "structure": float(adaptive.get("confluence_weight_structure", self.settings.confluence_weight_structure)),
                "momentum": float(adaptive.get("confluence_weight_momentum", self.settings.confluence_weight_momentum)),
                "volume": float(adaptive.get("confluence_weight_volume", self.settings.confluence_weight_volume)),
            },
            "feedback": {
                "exit_reason_performance": exit_reason_stats,
                "exit_type_performance": exit_type_stats,
                "tag_performance": tag_stats,
                "insights": insights,
            },
            "history_count": len(history),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_feedback(self, user_id: str = "system") -> dict:
        history = self.trade_history(user_id, limit=max(int(self.settings.analytics_history_limit), 1))
        summary = self.summary(user_id)
        closed = [trade for trade in history if str(trade.get("status", "CLOSED")).upper() == "CLOSED"]
        volume_reversal_trades = [
            trade for trade in closed if str(trade.get("exit_reason", "") or "") == "volume_reversal"
        ]
        early_exit_trades = [
            trade for trade in closed if str(trade.get("exit_type", "") or "") == "early_exit"
        ]
        strict_confluence_trades = [
            trade for trade in closed if "strict_confluence" in [str(tag).lower() for tag in trade.get("tags", [])]
        ]
        structure_success = self._win_rate(
            [
                trade
                for trade in strict_confluence_trades
                if "structure" in str(trade.get("entry_reason", "") or "").lower()
            ]
        )
        symbol_performance = self._symbol_performance(closed)
        best_symbols = self._best_symbols(closed)
        return {
            "history_count": len(closed),
            "volume_spike_losses": round(self._loss_rate(volume_reversal_trades), 8),
            "early_exit_missed_profit": round(self._early_exit_missed_profit_rate(early_exit_trades), 8),
            "structure_success": round(structure_success, 8),
            "false_signal_rate": round(self._false_signal_rate(closed), 8),
            "best_regime": str(summary.get("best_regime", "") or ""),
            "worst_regime": str(summary.get("worst_regime", "") or ""),
            "regime_win_rates": dict(summary.get("regime_win_rates", {}) or {}),
            "best_symbols": best_symbols,
            "symbol_performance": symbol_performance,
            "summary": summary,
        }

    def _bucket_performance(self, history: list[dict], *, key: str) -> dict[str, dict]:
        buckets: dict[str, list[float]] = {}
        for trade in history:
            bucket = str(trade.get(key, "") or "").strip()
            if not bucket:
                continue
            buckets.setdefault(bucket, []).append(float(trade.get("profit_pct", 0.0) or 0.0))
        result: dict[str, dict] = {}
        for bucket, profits in buckets.items():
            wins = [value for value in profits if value > 0]
            losses = [abs(value) for value in profits if value < 0]
            result[bucket] = {
                "trades": len(profits),
                "win_rate": round(len(wins) / max(len(profits), 1), 8),
                "avg_profit_pct": round(sum(profits) / max(len(profits), 1), 8),
                "avg_win": round(sum(wins) / max(len(wins), 1), 8) if wins else 0.0,
                "avg_loss": round(sum(losses) / max(len(losses), 1), 8) if losses else 0.0,
            }
        return result

    def _tag_performance(self, history: list[dict]) -> dict[str, dict]:
        buckets: dict[str, list[float]] = {}
        for trade in history:
            for tag in trade.get("tags", []):
                normalized = str(tag).strip().lower()
                if not normalized:
                    continue
                buckets.setdefault(normalized, []).append(float(trade.get("profit_pct", 0.0) or 0.0))
        result: dict[str, dict] = {}
        for tag, profits in buckets.items():
            wins = [value for value in profits if value > 0]
            result[tag] = {
                "trades": len(profits),
                "win_rate": round(len(wins) / max(len(profits), 1), 8),
                "avg_profit_pct": round(sum(profits) / max(len(profits), 1), 8),
            }
        return result

    def _insights(
        self,
        history: list[dict],
        summary: dict,
        exit_reason_stats: dict[str, dict],
        exit_type_stats: dict[str, dict],
        tag_stats: dict[str, dict],
    ) -> list[str]:
        insights: list[str] = []
        volume_reversal = exit_reason_stats.get("volume_reversal")
        if volume_reversal and volume_reversal["trades"] >= 3 and volume_reversal["win_rate"] < 0.5:
            insights.append("volume spike exits = mostly loss -> entry filter weak")
        early_exit = exit_type_stats.get("early_exit")
        if early_exit and early_exit["trades"] >= 3:
            missed = [
                max(0.0, float(trade.get("max_profit", 0.0) or 0.0) - float(trade.get("profit_pct", 0.0) or 0.0))
                for trade in history
                if str(trade.get("exit_type", "") or "") == "early_exit"
            ]
            if missed and (sum(missed) / max(len(missed), 1)) > 1.0:
                insights.append("early exit -> later big move -> exit too aggressive")
        divergence = tag_stats.get("mfi_divergence")
        if divergence and divergence["trades"] >= 3 and divergence["win_rate"] < float(summary.get("win_rate", 0.0) or 0.0):
            insights.append("MFI divergence trades = low win rate")
        return insights

    def _derive_tags(self, *, entry_reason: str, exit_reason: str, feature_snapshot: dict) -> list[str]:
        tags: set[str] = set()
        reason = entry_reason.lower()
        if "divergence" in reason:
            tags.add("mfi_divergence")
        if "liquidity sweep" in reason:
            tags.add("liquidity_sweep")
        if float(feature_snapshot.get("strict_trade_allowed", 0.0) or 0.0) >= 1.0:
            tags.add("strict_confluence")
        if exit_reason == "volume_reversal":
            tags.add("volume_reversal_exit")
        return sorted(tags)

    def _max_drawdown_pct(self, profits: list[float]) -> float:
        equity = 0.0
        peak = 0.0
        max_drawdown = 0.0
        for profit in profits:
            equity += float(profit)
            peak = max(peak, equity)
            max_drawdown = max(max_drawdown, peak - equity)
        return max_drawdown

    def _coerce_datetime(self, value) -> datetime:
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, str) and value.strip():
            try:
                parsed = datetime.fromisoformat(value)
                return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        return datetime.now(timezone.utc)

    def _history_key(self, user_id: str) -> str:
        return f"analytics:history:{user_id}"

    def _loss_rate(self, trades: list[dict]) -> float:
        if not trades:
            return 0.0
        losing = [trade for trade in trades if float(trade.get("profit_pct", 0.0) or 0.0) < 0.0]
        return len(losing) / max(len(trades), 1)

    def _win_rate(self, trades: list[dict]) -> float:
        if not trades:
            return 0.0
        winners = [trade for trade in trades if float(trade.get("profit_pct", 0.0) or 0.0) > 0.0]
        return len(winners) / max(len(trades), 1)

    def _early_exit_missed_profit_rate(self, trades: list[dict]) -> float:
        if not trades:
            return 0.0
        missed = [
            trade for trade in trades
            if float(trade.get("max_profit", 0.0) or 0.0) > float(trade.get("profit_pct", 0.0) or 0.0)
        ]
        return len(missed) / max(len(trades), 1)

    def _symbol_performance(self, history: list[dict]) -> dict[str, dict]:
        buckets: dict[str, list[dict]] = {}
        for trade in history:
            symbol = str(trade.get("symbol", "") or "").upper().strip()
            if not symbol:
                continue
            buckets.setdefault(symbol, []).append(trade)
        performance: dict[str, dict] = {}
        for symbol, trades in buckets.items():
            profits = [float(item.get("profit_pct", 0.0) or 0.0) for item in trades]
            performance[symbol] = {
                "trades": len(trades),
                "win_rate": round(self._win_rate(trades), 8),
                "avg_profit_pct": round(sum(profits) / max(len(profits), 1), 8),
                "net_profit_pct": round(sum(profits), 8),
            }
        return performance

    def _best_symbols(self, history: list[dict]) -> list[str]:
        performance = self._symbol_performance(history)
        ranked = sorted(
            performance.items(),
            key=lambda item: (
                float(item[1].get("win_rate", 0.0) or 0.0),
                float(item[1].get("avg_profit_pct", 0.0) or 0.0),
                float(item[1].get("trades", 0) or 0.0),
            ),
            reverse=True,
        )
        return [symbol for symbol, metrics in ranked if int(metrics.get("trades", 0) or 0) > 0][:3]

    def _worst_exit_reasons(self, history: list[dict]) -> list[str]:
        stats = self._bucket_performance(history, key="exit_reason")
        ranked = sorted(
            stats.items(),
            key=lambda item: (
                float(item[1].get("avg_profit_pct", 0.0) or 0.0),
                -float(item[1].get("trades", 0) or 0.0),
            ),
        )
        return [reason for reason, metrics in ranked if int(metrics.get("trades", 0) or 0) > 0][:3]

    def _most_profitable_setup(self, history: list[dict]) -> str:
        reason_buckets: dict[str, list[float]] = {}
        for trade in history:
            reason = str(trade.get("entry_reason", "") or "").strip()
            if not reason:
                continue
            normalized = " + ".join(part.strip() for part in reason.split("+") if part.strip())
            if not normalized:
                continue
            reason_buckets.setdefault(normalized, []).append(float(trade.get("profit_pct", 0.0) or 0.0))
        if not reason_buckets:
            return ""
        ranked = sorted(
            reason_buckets.items(),
            key=lambda item: (sum(item[1]) / max(len(item[1]), 1), len(item[1])),
            reverse=True,
        )
        return ranked[0][0]

    def _false_signal_rate(self, history: list[dict]) -> float:
        if not history:
            return 0.0
        false_signals = [
            trade
            for trade in history
            if float(trade.get("profit_pct", 0.0) or 0.0) < 0.0
            and float(trade.get("max_profit", 0.0) or 0.0) <= 0.5
        ]
        return len(false_signals) / max(len(history), 1)

    def _regime_win_rates(self, history: list[dict]) -> dict[str, float]:
        buckets: dict[str, list[dict]] = {}
        for trade in history:
            regime = str(trade.get("regime", "") or "").upper().strip()
            if not regime:
                continue
            buckets.setdefault(regime, []).append(trade)
        return {
            regime: round(self._win_rate(trades), 8)
            for regime, trades in sorted(buckets.items())
        }

    def _regime_edges(self, history: list[dict]) -> tuple[str, str]:
        buckets: dict[str, list[float]] = {}
        for trade in history:
            regime = str(trade.get("regime", "") or "").upper().strip()
            if not regime:
                continue
            buckets.setdefault(regime, []).append(float(trade.get("profit_pct", 0.0) or 0.0))
        if not buckets:
            return "", ""
        ranked = sorted(
            buckets.items(),
            key=lambda item: (sum(item[1]) / max(len(item[1]), 1), len(item[1])),
            reverse=True,
        )
        return ranked[0][0], ranked[-1][0]

    def _portfolio_metrics(self, user_id: str) -> dict[str, float]:
        active_trades = self.active_trades(user_id)
        gross_notional = sum(
            float(trade.get("entry", 0.0) or 0.0) * float(trade.get("executed_quantity", 0.0) or 0.0)
            for trade in active_trades
        )
        equity = max(float(self.settings.default_portfolio_balance), 1e-8)
        gross_exposure_pct = gross_notional / equity
        correlation_values = [
            float(trade.get("portfolio_correlation_risk", 0.0) or 0.0)
            for trade in active_trades
        ]
        correlation_risk = sum(correlation_values) / max(len(correlation_values), 1) if correlation_values else 0.0
        return {
            "capital_utilization": min(1.0, gross_exposure_pct / max(float(self.settings.max_portfolio_exposure_pct), 1e-8)),
            "risk_exposure": sum(float(trade.get("risk_fraction", 0.0) or 0.0) for trade in active_trades),
            "correlation_risk": correlation_risk,
        }

    def _regime_distribution(self, history: list[dict]) -> dict[str, float]:
        if not history:
            return {}
        counts: dict[str, int] = {}
        for trade in history:
            regime = str(trade.get("regime", "") or "").upper().strip()
            if not regime:
                continue
            counts[regime] = counts.get(regime, 0) + 1
        total = sum(counts.values())
        if total <= 0:
            return {}
        return {
            regime: round(count / total, 8)
            for regime, count in sorted(counts.items())
        }
