from __future__ import annotations

from dataclasses import dataclass
import hashlib

from app.core.config import Settings


@dataclass
class ShardManager:
    settings: Settings

    def shard_id(self, user_id: str) -> int:
        digest = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
        return int(digest[:12], 16) % max(self.settings.execution_shard_count, 1)

    def queue_priority(self, signal: dict, subscription: dict) -> str:
        alpha_score = float(signal.get("alpha_decision", {}).get("final_score", signal.get("alpha_score", 0.0)))
        probability = float(signal.get("trade_success_probability", signal.get("raw_trade_success_probability", 0.0)) or 0.0)
        sleeve_budget_delta = float(signal.get("factor_sleeve_budget_delta", 0.0) or 0.0)
        sleeve_recent_win_rate = float(signal.get("factor_sleeve_recent_win_rate", 0.5) or 0.0)
        sleeve_budget_turnover = float(signal.get("factor_sleeve_budget_turnover", 0.0) or 0.0)
        sleeve_budget_gap = float(signal.get("max_factor_sleeve_budget_gap_pct", 0.0) or 0.0)
        tier = str(subscription.get("tier", "free")).lower()
        risk_profile = str(subscription.get("risk_profile", "moderate")).lower()
        sleeve_priority_boost = (
            sleeve_budget_delta >= 0.08
            and sleeve_recent_win_rate >= 0.55
            and probability >= 0.60
            and sleeve_budget_turnover < self.settings.portfolio_concentration_soft_turnover
            and sleeve_budget_gap < self.settings.portfolio_concentration_soft_alert_drift
        )
        if alpha_score >= self.settings.high_priority_alpha_threshold and tier in {"vip", "institutional"}:
            return "high"
        if sleeve_priority_boost and tier in {"vip", "institutional"}:
            return "high"
        if tier == "free" or risk_profile == "conservative":
            if sleeve_priority_boost and risk_profile != "conservative":
                return "normal"
            return "delayed"
        return "normal"

    def execution_delay_ms(self, priority: str) -> int:
        if priority == "high":
            return self.settings.randomized_execution_delay_min_ms
        if priority == "delayed":
            return self.settings.delayed_queue_min_ms
        return self.settings.randomized_execution_delay_max_ms

    def group_users(self, subscriptions: list[dict]) -> dict[int, list[dict]]:
        grouped: dict[int, list[dict]] = {}
        for subscription in subscriptions:
            shard = self.shard_id(str(subscription["user_id"]))
            grouped.setdefault(shard, []).append(subscription)
        return grouped
