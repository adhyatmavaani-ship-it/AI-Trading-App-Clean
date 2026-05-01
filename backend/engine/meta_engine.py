from __future__ import annotations

from backend.db.database import SQLiteTradeDatabase
from backend.models.trade import MetaDecision, SignalPayload, StrategyPerformance


class MetaEngine:
    def __init__(
        self,
        db: SQLiteTradeDatabase,
        *,
        last_n_trades: int = 20,
        min_history: int = 3,
        recent_trade_window: int = 10,
        weak_strategy_threshold: float = 0.2,
        kill_switch_score: float = 0.0,
    ) -> None:
        self._db = db
        self._last_n_trades = last_n_trades
        self._min_history = min_history
        self._recent_trade_window = recent_trade_window
        self._weak_strategy_threshold = weak_strategy_threshold
        self._kill_switch_score = kill_switch_score

    def evaluate_signal(
        self,
        signal: SignalPayload,
        candidate_strategies: list[str],
    ) -> MetaDecision:
        strategies = sorted(set(candidate_strategies + self._db.strategy_names() + [signal.strategy]))
        performance = [self._summarize_strategy(name) for name in strategies]
        performance_by_name = {item.strategy: item for item in performance}
        current = next(item for item in performance if item.strategy == signal.strategy)
        selected_strategy, _scores = self.select_best_strategy(strategies, performance=performance)
        best = performance_by_name.get(selected_strategy) if selected_strategy is not None else None

        if current.score < self._kill_switch_score:
            return MetaDecision(
                approved=False,
                selected_strategy=selected_strategy,
                score=current.score,
                confidence=current.confidence,
                reason="strategy_disabled_by_kill_switch",
                performance=performance,
            )

        if best is None:
            allow_bootstrap = current.total_trades < self._min_history and current.score >= self._kill_switch_score
            return MetaDecision(
                approved=allow_bootstrap,
                selected_strategy=current.strategy if allow_bootstrap else None,
                score=current.score,
                confidence=current.confidence,
                reason="bootstrap_strategy_allowed" if allow_bootstrap else "no_strategy_above_threshold",
                performance=performance,
            )

        if current.total_trades < self._min_history and current.strategy == best.strategy:
            return MetaDecision(
                approved=True,
                selected_strategy=best.strategy,
                score=current.score,
                confidence=current.confidence,
                reason="insufficient_history_but_best_recent_candidate",
                performance=performance,
            )

        approved = current.strategy == best.strategy and current.score >= self._weak_strategy_threshold
        reason = "strategy_selected_by_meta_engine" if approved else "better_strategy_available"
        return MetaDecision(
            approved=approved,
            selected_strategy=best.strategy,
            score=current.score,
            confidence=current.confidence,
            reason=reason,
            performance=performance,
        )

    def calculate_score(self, strategy: str) -> float:
        return self._summarize_strategy(strategy).score

    def select_best_strategy(
        self,
        strategies: list[str],
        *,
        performance: list[StrategyPerformance] | None = None,
    ) -> tuple[str | None, dict[str, float]]:
        summaries = performance or [self._summarize_strategy(name) for name in strategies]
        scores = {item.strategy: item.score for item in summaries}
        valid = {
            item.strategy: item.score
            for item in summaries
            if item.score > self._weak_strategy_threshold and not item.disabled
        }
        if not valid:
            return None, scores
        best = max(valid, key=valid.get)
        return best, scores

    def _stats(self, trades: list[tuple[float, str]]) -> tuple[float, float, float]:
        wins = [pnl for pnl, result in trades if result == "win"]
        losses = [abs(pnl) for pnl, result in trades if result == "loss"]
        total = len(trades)
        win_rate = len(wins) / total if total else 0.0
        gross_profit = sum(wins)
        gross_loss = sum(losses)
        profit_factor = gross_profit / gross_loss if gross_loss else gross_profit
        drawdown = len(losses) / total if total else 0.0
        return win_rate, profit_factor, drawdown

    def _summarize_strategy(self, strategy: str) -> StrategyPerformance:
        trades = self._db.get_recent_trades(strategy, limit=self._last_n_trades)
        outcome_trades = [trade for trade in trades if trade[1] in {"win", "loss"}]
        if not outcome_trades:
            return StrategyPerformance(strategy=strategy)

        total_trades = len(outcome_trades)
        recent = outcome_trades[: self._recent_trade_window]
        older = outcome_trades[self._recent_trade_window :]
        recent_win_rate, profit_factor, recent_drawdown = self._stats(recent)
        overall_win_rate, _overall_pf, overall_drawdown = self._stats(outcome_trades)
        older_win_rate, _older_pf, _older_drawdown = self._stats(older)
        momentum = recent_win_rate - older_win_rate if older else recent_win_rate
        score = (
            (recent_win_rate * 0.5)
            + (profit_factor * 0.3)
            + (momentum * 0.2)
            - (recent_drawdown * 0.2)
        )
        confidence = max(0.0, min(round(score, 4), 1.0))
        disabled = score < self._kill_switch_score

        return StrategyPerformance(
            strategy=strategy,
            total_trades=total_trades,
            win_rate=overall_win_rate,
            recent_win_rate=recent_win_rate,
            profit_factor=profit_factor,
            momentum=momentum,
            drawdown=overall_drawdown,
            score=round(score, 4),
            confidence=confidence,
            disabled=disabled,
        )
