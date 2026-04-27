from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math

from app.core.config import Settings
from app.core.exceptions import StateError
from app.services.redis_cache import RedisCache


@dataclass
class PortfolioLedgerService:
    settings: Settings
    cache: RedisCache
    market_data: any
    redis_state_manager: any
    firestore: any | None = None

    def load_summary(self, user_id: str) -> dict:
        summary = self.cache.get_json(self._summary_key(user_id))
        if summary:
            return summary
        starting_equity = float(self.settings.default_portfolio_balance)
        return {
            "user_id": user_id,
            "starting_equity": starting_equity,
            "realized_pnl": 0.0,
            "realized_equity": starting_equity,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "winning_trades": 0,
            "losing_trades": 0,
            "closed_trades": 0,
            "fees_paid": 0.0,
            "total_volume": 0.0,
            "mark_to_market_peak_equity": starting_equity,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def record_trade_open(
        self,
        *,
        user_id: str,
        trade_id: str,
        symbol: str,
        side: str,
        entry_price: float,
        executed_quantity: float,
        notional: float,
        fee_paid: float,
    ) -> None:
        summary = self.load_summary(user_id)
        summary["fees_paid"] = round(float(summary.get("fees_paid", 0.0)) + fee_paid, 8)
        summary["total_volume"] = round(float(summary.get("total_volume", 0.0)) + notional, 8)
        summary["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._persist_summary(user_id, summary)

        active_index = self._load_active_index(user_id)
        if trade_id not in active_index:
            active_index.append(trade_id)
            self.cache.set_json(
                self._active_index_key(user_id),
                {"trade_ids": active_index},
                ttl=self.settings.monitor_state_ttl_seconds,
            )
        self._invalidate_snapshot(user_id)
        self._persist_portfolio_metrics(
            user_id,
            {
                "symbol": symbol,
                "side": side,
                "entry_price": entry_price,
                "executed_quantity": executed_quantity,
                "notional": notional,
                "event": "trade_open",
            },
        )

    def record_trade_close(self, *, user_id: str, trade_id: str, pnl: float) -> dict:
        summary = self.load_summary(user_id)
        trade = self.redis_state_manager.load_active_trade(trade_id) or {}
        summary["realized_pnl"] = round(float(summary.get("realized_pnl", 0.0)) + pnl, 8)
        summary["realized_equity"] = round(float(summary["starting_equity"]) + float(summary["realized_pnl"]), 8)
        summary["gross_profit"] = round(float(summary.get("gross_profit", 0.0)) + max(0.0, pnl), 8)
        summary["gross_loss"] = round(float(summary.get("gross_loss", 0.0)) + abs(min(0.0, pnl)), 8)
        summary["closed_trades"] = int(summary.get("closed_trades", 0)) + 1
        summary["winning_trades"] = int(summary.get("winning_trades", 0)) + int(pnl > 0)
        summary["losing_trades"] = int(summary.get("losing_trades", 0)) + int(pnl < 0)
        summary["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._persist_summary(user_id, summary)

        active_index = [current_trade_id for current_trade_id in self._load_active_index(user_id) if current_trade_id != trade_id]
        self.cache.set_json(
            self._active_index_key(user_id),
            {"trade_ids": active_index},
            ttl=self.settings.monitor_state_ttl_seconds,
        )
        self._invalidate_snapshot(user_id)
        self._persist_portfolio_metrics(
            user_id,
            {
                "trade_id": trade_id,
                "realized_pnl": pnl,
                "event": "trade_close",
            },
        )
        self._record_factor_sleeve_outcome(
            user_id=user_id,
            symbol=str(trade.get("symbol", "")),
            pnl=pnl,
        )
        return summary

    def close_trade(
        self,
        *,
        user_id: str,
        trade_id: str,
        exit_price: float,
        closed_quantity: float | None = None,
        exit_fee: float = 0.0,
    ) -> dict:
        trade = self.redis_state_manager.load_active_trade(trade_id)
        if trade is None:
            raise ValueError(f"Active trade {trade_id} was not found")
        if trade.get("user_id") != user_id:
            raise ValueError("Trade does not belong to the requested user")
        if str(trade.get("status", "")).upper() == "CLOSED":
            raise StateError(
                "Trade is already closed",
                error_code="TRADE_ALREADY_CLOSED",
            )

        entry_price = float(trade.get("entry", 0.0) or 0.0)
        side = str(trade.get("side", "BUY")).upper()
        open_quantity = float(trade.get("executed_quantity", trade.get("allocated_quantity", 0.0)) or 0.0)
        if open_quantity <= 0:
            raise ValueError("Trade has no remaining open quantity")
        quantity_to_close = min(open_quantity, float(closed_quantity or open_quantity))
        if quantity_to_close <= 0:
            raise ValueError("closed_quantity must be positive")
        fee_paid = float(trade.get("fees", trade.get("fee_paid", 0.0)) or 0.0)
        entry_fee_allocated = fee_paid * (quantity_to_close / max(open_quantity, 1e-8))
        direction = 1.0 if side == "BUY" else -1.0
        realized_pnl = ((exit_price - entry_price) * quantity_to_close * direction) - entry_fee_allocated - exit_fee

        remaining_quantity = max(0.0, open_quantity - quantity_to_close)
        remaining_fee = max(0.0, fee_paid - entry_fee_allocated)
        remaining_notional = remaining_quantity * entry_price
        updated_trade = dict(trade)
        if remaining_quantity > 0:
            updated_trade["executed_quantity"] = round(remaining_quantity, 8)
            updated_trade["notional"] = round(remaining_notional, 8)
            updated_trade["fees"] = round(remaining_fee, 8)
            updated_trade["status"] = "PARTIAL"
            updated_trade["partial_closes"] = int(trade.get("partial_closes", 0)) + 1
            updated_trade["realized_pnl_booked"] = round(float(trade.get("realized_pnl_booked", 0.0)) + realized_pnl, 8)
            updated_trade["last_exit_price"] = round(exit_price, 8)
            updated_trade["last_exit_fee"] = round(exit_fee, 8)
        else:
            updated_trade["status"] = "CLOSED"
            updated_trade["executed_quantity"] = 0.0
            updated_trade["notional"] = 0.0
            updated_trade["fees"] = round(remaining_fee, 8)
            updated_trade["last_exit_price"] = round(exit_price, 8)
            updated_trade["last_exit_fee"] = round(exit_fee, 8)

        summary = self.load_summary(user_id)
        summary["realized_pnl"] = round(float(summary.get("realized_pnl", 0.0)) + realized_pnl, 8)
        summary["realized_equity"] = round(float(summary["starting_equity"]) + float(summary["realized_pnl"]), 8)
        summary["gross_profit"] = round(float(summary.get("gross_profit", 0.0)) + max(0.0, realized_pnl), 8)
        summary["gross_loss"] = round(float(summary.get("gross_loss", 0.0)) + abs(min(0.0, realized_pnl)), 8)
        summary["winning_trades"] = int(summary.get("winning_trades", 0)) + int(realized_pnl > 0 and remaining_quantity == 0)
        summary["losing_trades"] = int(summary.get("losing_trades", 0)) + int(realized_pnl < 0 and remaining_quantity == 0)
        summary["closed_trades"] = int(summary.get("closed_trades", 0)) + int(remaining_quantity == 0)
        summary["fees_paid"] = round(float(summary.get("fees_paid", 0.0)) + exit_fee, 8)
        summary["total_volume"] = round(float(summary.get("total_volume", 0.0)) + (quantity_to_close * exit_price), 8)
        summary["updated_at"] = datetime.now(timezone.utc).isoformat()

        active_index = self._load_active_index(user_id)
        if remaining_quantity <= 0:
            active_index = [current_trade_id for current_trade_id in active_index if current_trade_id != trade_id]
        elif trade_id not in active_index:
            active_index.append(trade_id)
        if hasattr(self.cache, "client"):
            pipeline = self.cache.client.pipeline(transaction=True)
            pipeline.setex(
                self._summary_key(user_id),
                self.settings.monitor_state_ttl_seconds,
                json.dumps(summary),
            )
            pipeline.setex(
                self._active_index_key(user_id),
                self.settings.monitor_state_ttl_seconds,
                json.dumps({"trade_ids": active_index}),
            )
            if remaining_quantity > 0:
                pipeline.setex(
                    f"active_trade:{trade_id}",
                    self.settings.monitor_state_ttl_seconds,
                    json.dumps(updated_trade),
                )
            else:
                pipeline.delete(f"active_trade:{trade_id}")
            pipeline.delete(self._snapshot_key(user_id))
            pipeline.execute()
        else:
            self._persist_summary(user_id, summary)
            self.cache.set_json(
                self._active_index_key(user_id),
                {"trade_ids": active_index},
                ttl=self.settings.monitor_state_ttl_seconds,
            )
            if remaining_quantity > 0:
                self.redis_state_manager.save_active_trade(trade_id, updated_trade)
            else:
                self.redis_state_manager.clear_active_trade(trade_id)
            self._invalidate_snapshot(user_id)

        payload = {
            "trade_id": trade_id,
            "symbol": str(updated_trade.get("symbol", "")),
            "side": side,
            "closed_quantity": round(quantity_to_close, 8),
            "remaining_quantity": round(remaining_quantity, 8),
            "exit_price": round(exit_price, 8),
            "exit_fee": round(exit_fee, 8),
            "realized_pnl": round(realized_pnl, 8),
            "status": "PARTIAL" if remaining_quantity > 0 else "CLOSED",
            "current_equity": float(summary["realized_equity"]),
            "entry_fee_allocated": round(entry_fee_allocated, 8),
        }
        self._persist_portfolio_metrics(
            user_id,
            {
                **payload,
                "event": "partial_close" if remaining_quantity > 0 else "trade_close",
            },
        )
        self._record_factor_sleeve_outcome(
            user_id=user_id,
            symbol=str(updated_trade.get("symbol", "")),
            pnl=realized_pnl,
        )
        return payload

    async def portfolio_snapshot(self, user_id: str) -> dict:
        cached = self.cache.get_json(self._snapshot_key(user_id))
        if cached:
            return cached

        summary = self.load_summary(user_id)
        active_trades = self._load_active_trades(user_id)
        price_map = await self._fetch_prices(active_trades)
        positions: dict[tuple[str, str], dict] = {}
        unrealized_pnl = 0.0
        open_notional = 0.0
        gross_exposure = 0.0

        for trade in active_trades:
            symbol = str(trade.get("symbol", "")).upper()
            side = str(trade.get("side", "BUY")).upper()
            entry_price = float(trade.get("entry", 0.0) or 0.0)
            quantity = float(trade.get("executed_quantity", trade.get("allocated_quantity", 0.0)) or 0.0)
            fee_paid = float(trade.get("fees", trade.get("fee_paid", 0.0)) or 0.0)
            mark_price = float(price_map.get(symbol, entry_price) or entry_price)
            direction = 1.0 if side == "BUY" else -1.0
            trade_unrealized = ((mark_price - entry_price) * quantity * direction) - fee_paid
            unrealized_pnl += trade_unrealized
            open_notional += entry_price * quantity
            gross_exposure += abs(mark_price * quantity)

            key = (symbol, side)
            position = positions.setdefault(
                key,
                {
                    "symbol": symbol,
                    "side": side,
                    "quantity": 0.0,
                    "entry_notional": 0.0,
                    "current_price": mark_price,
                    "market_value": 0.0,
                    "unrealized_pnl": 0.0,
                    "trade_count": 0,
                },
            )
            position["quantity"] += quantity
            position["entry_notional"] += entry_price * quantity
            position["current_price"] = mark_price
            position["market_value"] += mark_price * quantity
            position["unrealized_pnl"] += trade_unrealized
            position["trade_count"] += 1

        position_items: list[dict] = []
        for position in positions.values():
            quantity = max(position["quantity"], 1e-8)
            avg_entry_price = position["entry_notional"] / quantity
            position_items.append(
                {
                    "symbol": position["symbol"],
                    "side": position["side"],
                    "quantity": round(position["quantity"], 8),
                    "avg_entry_price": round(avg_entry_price, 8),
                    "current_price": round(position["current_price"], 8),
                    "market_value": round(position["market_value"], 8),
                    "unrealized_pnl": round(position["unrealized_pnl"], 8),
                    "trade_count": int(position["trade_count"]),
                }
            )

        current_equity = round(float(summary["realized_equity"]) + unrealized_pnl, 8)
        peak_equity = max(float(summary.get("mark_to_market_peak_equity", summary["starting_equity"])), current_equity)
        rolling_drawdown = max(0.0, (peak_equity - current_equity) / max(peak_equity, 1e-8))
        if peak_equity > float(summary.get("mark_to_market_peak_equity", 0.0)):
            summary["mark_to_market_peak_equity"] = peak_equity
            summary["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._persist_summary(user_id, summary)

        snapshot = {
            "user_id": user_id,
            "starting_equity": float(summary["starting_equity"]),
            "realized_equity": float(summary["realized_equity"]),
            "current_equity": current_equity,
            "absolute_pnl": round(current_equity - float(summary["starting_equity"]), 8),
            "pnl_pct": round((current_equity - float(summary["starting_equity"])) / max(float(summary["starting_equity"]), 1e-8), 8),
            "realized_pnl": round(float(summary["realized_pnl"]), 8),
            "unrealized_pnl": round(unrealized_pnl, 8),
            "gross_profit": round(float(summary["gross_profit"]), 8),
            "gross_loss": round(float(summary["gross_loss"]), 8),
            "winning_trades": int(summary["winning_trades"]),
            "losing_trades": int(summary["losing_trades"]),
            "closed_trades": int(summary["closed_trades"]),
            "active_trades": len(active_trades),
            "open_notional": round(open_notional, 8),
            "gross_exposure": round(gross_exposure, 8),
            "fees_paid": round(float(summary["fees_paid"]), 8),
            "peak_equity": round(peak_equity, 8),
            "rolling_drawdown": round(rolling_drawdown, 8),
            "positions": sorted(position_items, key=lambda item: (item["symbol"], item["side"])),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.cache.set_json(
            self._snapshot_key(user_id),
            snapshot,
            ttl=self.settings.portfolio_snapshot_cache_ttl_seconds,
        )
        return snapshot

    def portfolio_risk_summary(self, user_id: str) -> dict:
        active_trades = self._load_active_trades(user_id)
        summary = self.load_summary(user_id)
        equity = max(float(summary.get("realized_equity", self.settings.default_portfolio_balance)), 1e-8)
        symbol_exposures: dict[str, float] = {}
        side_exposures: dict[str, float] = {}
        theme_exposures: dict[str, float] = {}
        gross_exposure = 0.0
        for trade in active_trades:
            symbol = str(trade.get("symbol", "")).upper()
            side = str(trade.get("side", "BUY")).upper()
            theme = self.theme_for_symbol(symbol)
            quantity = float(trade.get("executed_quantity", trade.get("allocated_quantity", 0.0)) or 0.0)
            entry_price = float(trade.get("entry", 0.0) or 0.0)
            notional = abs(float(trade.get("notional", entry_price * quantity) or 0.0))
            gross_exposure += notional
            if symbol:
                symbol_exposures[symbol] = round(symbol_exposures.get(symbol, 0.0) + notional, 8)
            side_exposures[side] = round(side_exposures.get(side, 0.0) + notional, 8)
            theme_exposures[theme] = round(theme_exposures.get(theme, 0.0) + notional, 8)
        return {
            "user_id": user_id,
            "active_trades": len(active_trades),
            "gross_exposure": round(gross_exposure, 8),
            "gross_exposure_pct": round(gross_exposure / equity, 8),
            "symbol_exposures": symbol_exposures,
            "symbol_exposure_pct": {
                symbol: round(notional / equity, 8)
                for symbol, notional in symbol_exposures.items()
            },
            "side_exposures": side_exposures,
            "side_exposure_pct": {
                side: round(notional / equity, 8)
                for side, notional in side_exposures.items()
            },
            "theme_exposures": theme_exposures,
            "theme_exposure_pct": {
                theme: round(notional / equity, 8)
                for theme, notional in theme_exposures.items()
            },
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def portfolio_concentration_profile(self, user_id: str, candidate_symbol: str | None = None) -> dict:
        summary = self.portfolio_risk_summary(user_id)
        active_symbols = sorted((summary.get("symbol_exposures") or {}).keys())
        candidate_symbol = str(candidate_symbol or "").upper().strip() or None
        symbols_for_analysis = list(active_symbols)
        if candidate_symbol and candidate_symbol not in symbols_for_analysis:
            symbols_for_analysis.append(candidate_symbol)

        if not symbols_for_analysis:
            return {
                **summary,
                "cluster_assignments": {},
                "cluster_exposures": {},
                "cluster_exposure_pct": {},
                "beta_bucket_assignments": {},
                "beta_bucket_exposures": {},
                "beta_bucket_exposure_pct": {},
                "factor_regime": "RANGING",
                "factor_model": "pca_covariance_regime_universe_v1",
                "factor_universe_symbols": [],
                "factor_weights": {},
                "factor_attribution": {},
                "dominant_factor_sleeve": None,
                "factor_sleeve_performance": {},
                "factor_sleeve_budget_targets": {},
                "factor_sleeve_budget_deltas": {},
                "factor_sleeve_budget_turnover": 0.0,
                "max_factor_sleeve_budget_gap_pct": 0.0,
                "dominant_over_budget_sleeve": None,
                "dominant_under_budget_sleeve": None,
                "candidate_cluster_exposure_pct": 0.0,
                "candidate_beta_bucket_exposure_pct": 0.0,
                "candidate_theme_exposure_pct": 0.0,
            }

        returns_map = await self._returns_map(symbols_for_analysis)
        cluster_assignments = self._cluster_assignments(returns_map)
        cluster_exposures = self._aggregate_group_exposures(
            symbol_exposures=summary.get("symbol_exposures") or {},
            assignments=cluster_assignments,
        )
        beta_bucket_assignments, factor_weights, factor_regime, factor_universe_symbols = await self._beta_bucket_assignments(
            symbols_for_analysis,
            returns_map,
            symbol_exposures=summary.get("symbol_exposures") or {},
            candidate_symbol=candidate_symbol,
        )
        beta_bucket_exposures = self._aggregate_group_exposures(
            symbol_exposures=summary.get("symbol_exposures") or {},
            assignments=beta_bucket_assignments,
        )
        equity = max(float(self.load_summary(user_id).get("realized_equity", self.settings.default_portfolio_balance)), 1e-8)
        cluster_exposure_pct = {
            cluster: round(notional / equity, 8)
            for cluster, notional in cluster_exposures.items()
        }
        beta_bucket_exposure_pct = {
            bucket: round(notional / equity, 8)
            for bucket, notional in beta_bucket_exposures.items()
        }
        factor_attribution = self._factor_attribution(
            symbol_exposure_pct=summary.get("symbol_exposure_pct") or {},
            factor_weights=factor_weights,
        )
        factor_sleeve_performance = self.sleeve_performance_summary(user_id)
        factor_sleeve_budget_targets, factor_sleeve_budget_deltas = self._factor_sleeve_budgets(
            factor_attribution=factor_attribution,
            factor_sleeve_performance=factor_sleeve_performance,
        )
        (
            max_factor_sleeve_budget_gap_pct,
            dominant_over_budget_sleeve,
            dominant_under_budget_sleeve,
        ) = self._budget_gap_summary(factor_sleeve_budget_deltas)
        candidate_theme = self.theme_for_symbol(candidate_symbol or "")
        candidate_cluster = cluster_assignments.get(candidate_symbol) if candidate_symbol else None
        candidate_beta_bucket = beta_bucket_assignments.get(candidate_symbol) if candidate_symbol else None

        previous_profile = self.latest_concentration_profile(user_id)
        profile = {
            **summary,
            "cluster_assignments": cluster_assignments,
            "cluster_exposures": cluster_exposures,
            "cluster_exposure_pct": cluster_exposure_pct,
            "beta_bucket_assignments": beta_bucket_assignments,
            "beta_bucket_exposures": beta_bucket_exposures,
            "beta_bucket_exposure_pct": beta_bucket_exposure_pct,
            "factor_regime": factor_regime,
            "factor_model": "pca_covariance_regime_universe_v1",
            "factor_universe_symbols": factor_universe_symbols,
            "factor_weights": factor_weights,
            "factor_attribution": factor_attribution,
            "dominant_factor_sleeve": max(factor_attribution, key=factor_attribution.get) if factor_attribution else None,
            "factor_sleeve_performance": factor_sleeve_performance,
            "factor_sleeve_budget_targets": factor_sleeve_budget_targets,
            "factor_sleeve_budget_deltas": factor_sleeve_budget_deltas,
            "max_factor_sleeve_budget_gap_pct": max_factor_sleeve_budget_gap_pct,
            "dominant_over_budget_sleeve": dominant_over_budget_sleeve,
            "dominant_under_budget_sleeve": dominant_under_budget_sleeve,
            "candidate_theme": candidate_theme,
            "candidate_cluster": candidate_cluster,
            "candidate_beta_bucket": candidate_beta_bucket,
            "candidate_theme_exposure_pct": float((summary.get("theme_exposure_pct") or {}).get(candidate_theme, 0.0)),
            "candidate_cluster_exposure_pct": float(cluster_exposure_pct.get(candidate_cluster or "", 0.0)),
            "candidate_beta_bucket_exposure_pct": float(beta_bucket_exposure_pct.get(candidate_beta_bucket or "", 0.0)),
        }
        profile.update(self._concentration_drift(profile, previous_profile))
        self._persist_concentration_profile(user_id, profile)
        return profile

    def latest_concentration_profile(self, user_id: str) -> dict:
        return self.cache.get_json(self._concentration_profile_key(user_id)) or {}

    def concentration_history(self, user_id: str) -> list[dict]:
        bucket = self.cache.get_json(self._concentration_history_key(user_id)) or {}
        return list(bucket.get("snapshots", []))

    def factor_attribution_history(self, user_id: str) -> list[dict]:
        bucket = self.cache.get_json(self._factor_history_key(user_id)) or {}
        return list(bucket.get("snapshots", []))

    def sleeve_performance_summary(self, user_id: str) -> dict[str, dict]:
        bucket = self.cache.get_json(self._factor_performance_key(user_id)) or {}
        return dict(bucket.get("sleeves", {}))

    def theme_for_symbol(self, symbol: str) -> str:
        normalized_symbol = str(symbol or "").upper()
        base_asset = self._base_asset(normalized_symbol)
        theme_map = self._theme_map()
        for theme, assets in theme_map.items():
            if base_asset in assets:
                return theme
        return "OTHER"

    def _load_active_trades(self, user_id: str) -> list[dict]:
        active_trades: list[dict] = []
        indexed_trade_ids = self._load_active_index(user_id)
        active_index_changed = False
        for trade_id in indexed_trade_ids:
            trade = self.redis_state_manager.load_active_trade(trade_id)
            if trade is None:
                active_index_changed = True
                continue
            if trade.get("user_id") != user_id:
                active_index_changed = True
                continue
            active_trades.append(trade)
        if not active_trades:
            fallback_trades = [
                trade
                for trade in self.redis_state_manager.restore_active_trades()
                if str(trade.get("user_id", "") or "") == user_id
            ]
            if fallback_trades:
                active_trades = fallback_trades
                active_index_changed = True
        if active_index_changed:
            self.cache.set_json(
                self._active_index_key(user_id),
                {"trade_ids": [trade["trade_id"] for trade in active_trades]},
                ttl=self.settings.monitor_state_ttl_seconds,
            )
        return active_trades

    async def _fetch_prices(self, active_trades: list[dict]) -> dict[str, float]:
        unique_symbols = sorted({str(trade.get("symbol", "")).upper() for trade in active_trades if trade.get("symbol")})
        if not unique_symbols:
            return {}
        stream_prices: dict[str, float] = {}
        unresolved_symbols: list[str] = []
        for symbol in unique_symbols:
            cached_price = self.market_data.latest_stream_price(symbol) if hasattr(self.market_data, "latest_stream_price") else None
            if cached_price is not None:
                stream_prices[symbol] = float(cached_price)
            else:
                unresolved_symbols.append(symbol)
        fetched_prices: dict[str, float] = {}
        if unresolved_symbols:
            responses = await asyncio.gather(
                *(self.market_data.fetch_latest_price(symbol) for symbol in unresolved_symbols),
                return_exceptions=True,
            )
            for symbol, payload in zip(unresolved_symbols, responses, strict=False):
                if isinstance(payload, Exception):
                    continue
                fetched_prices[symbol] = float(payload)
        prices = {**stream_prices, **fetched_prices}
        for trade in active_trades:
            symbol = str(trade.get("symbol", "")).upper()
            prices.setdefault(symbol, float(trade.get("entry", 0.0) or 0.0))
        return prices

    def _persist_summary(self, user_id: str, payload: dict) -> None:
        self.cache.set_json(self._summary_key(user_id), payload, ttl=self.settings.monitor_state_ttl_seconds)

    def _persist_portfolio_metrics(self, user_id: str, payload: dict) -> None:
        if self.firestore is None or not hasattr(self.firestore, "save_performance_snapshot"):
            return
        self.firestore.save_performance_snapshot(
            f"portfolio:{user_id}",
            {
                **self.load_summary(user_id),
                **payload,
            },
        )

    def _invalidate_snapshot(self, user_id: str) -> None:
        self.cache.delete(self._snapshot_key(user_id))

    def _load_active_index(self, user_id: str) -> list[str]:
        payload = self.cache.get_json(self._active_index_key(user_id)) or {}
        return list(payload.get("trade_ids", []))

    def _summary_key(self, user_id: str) -> str:
        return f"portfolio:summary:{user_id}"

    def _snapshot_key(self, user_id: str) -> str:
        return f"portfolio:snapshot:{user_id}"

    def _active_index_key(self, user_id: str) -> str:
        return f"portfolio:active:{user_id}"

    def _concentration_profile_key(self, user_id: str) -> str:
        return f"portfolio:concentration:{user_id}"

    def _concentration_history_key(self, user_id: str) -> str:
        return f"portfolio:concentration_history:{user_id}"

    def _factor_history_key(self, user_id: str) -> str:
        return f"portfolio:factor_history:{user_id}"

    def _factor_performance_key(self, user_id: str) -> str:
        return f"portfolio:factor_performance:{user_id}"

    def _factor_performance_window_key(self, user_id: str) -> str:
        return f"portfolio:factor_performance_window:{user_id}"

    async def _returns_map(self, symbols: list[str]) -> dict[str, list[float]]:
        if not hasattr(self.market_data, "fetch_multi_timeframe_ohlcv"):
            return {}
        responses = await asyncio.gather(
            *(self.market_data.fetch_multi_timeframe_ohlcv(symbol, intervals=("15m",)) for symbol in symbols),
            return_exceptions=True,
        )
        returns_map: dict[str, list[float]] = {}
        for symbol, payload in zip(symbols, responses, strict=False):
            if isinstance(payload, Exception):
                continue
            returns = self._close_returns(payload)
            if returns:
                returns_map[symbol] = returns
        return returns_map

    def _close_returns(self, frames: dict | None) -> list[float]:
        if not frames:
            return []
        frame = frames.get("15m")
        if frame is None or "close" not in frame:
            return []
        closes = frame["close"].astype(float)
        returns = closes.pct_change().dropna().tail(self.settings.portfolio_correlation_lookback_candles)
        return [float(value) for value in returns.tolist() if math.isfinite(float(value))]

    def _correlation(self, left: list[float], right: list[float]) -> float | None:
        overlap = min(len(left), len(right), self.settings.portfolio_correlation_lookback_candles)
        if overlap < self.settings.portfolio_correlation_min_overlap:
            return None
        x = left[-overlap:]
        y = right[-overlap:]
        mean_x = sum(x) / overlap
        mean_y = sum(y) / overlap
        covariance = sum((lhs - mean_x) * (rhs - mean_y) for lhs, rhs in zip(x, y, strict=False))
        variance_x = sum((lhs - mean_x) ** 2 for lhs in x)
        variance_y = sum((rhs - mean_y) ** 2 for rhs in y)
        if variance_x <= 0 or variance_y <= 0:
            return None
        correlation = covariance / math.sqrt(variance_x * variance_y)
        if not math.isfinite(correlation):
            return None
        return float(correlation)

    def _cluster_assignments(self, returns_map: dict[str, list[float]]) -> dict[str, str]:
        symbols = sorted(returns_map.keys())
        if not symbols:
            return {}
        threshold = float(self.settings.portfolio_cluster_correlation_threshold)
        adjacency = {symbol: set() for symbol in symbols}
        for index, left_symbol in enumerate(symbols):
            for right_symbol in symbols[index + 1 :]:
                correlation = self._correlation(returns_map[left_symbol], returns_map[right_symbol])
                if correlation is None:
                    continue
                if abs(correlation) >= threshold:
                    adjacency[left_symbol].add(right_symbol)
                    adjacency[right_symbol].add(left_symbol)
        assignments: dict[str, str] = {}
        cluster_index = 1
        for symbol in symbols:
            if symbol in assignments:
                continue
            cluster_name = f"CLUSTER_{cluster_index}"
            stack = [symbol]
            while stack:
                current = stack.pop()
                if current in assignments:
                    continue
                assignments[current] = cluster_name
                stack.extend(sorted(adjacency[current] - set(assignments.keys())))
            cluster_index += 1
        return assignments

    async def _beta_bucket_assignments(
        self,
        symbols: list[str],
        returns_map: dict[str, list[float]],
        *,
        symbol_exposures: dict[str, float],
        candidate_symbol: str | None,
    ) -> tuple[dict[str, str], dict[str, float], str, list[str]]:
        if not symbols:
            return {}, {}, "RANGING", []
        basket_symbols = self._factor_basket_symbols(
            symbol_exposures=symbol_exposures,
            candidate_symbol=candidate_symbol,
            symbols_for_analysis=symbols,
        )
        for factor_symbol in basket_symbols:
            if factor_symbol in returns_map or not hasattr(self.market_data, "fetch_multi_timeframe_ohlcv"):
                continue
            try:
                factor_frames = await self.market_data.fetch_multi_timeframe_ohlcv(factor_symbol, intervals=("15m",))
            except Exception:
                continue
            factor_returns = self._close_returns(factor_frames)
            if factor_returns:
                returns_map[factor_symbol] = factor_returns
        benchmark_returns, factor_weights, factor_regime = self._market_factor_profile(
            {symbol: returns_map[symbol] for symbol in basket_symbols if symbol in returns_map}
        )
        if not benchmark_returns:
            return ({symbol: "BETA_UNKNOWN" for symbol in symbols}, factor_weights, factor_regime, basket_symbols)
        assignments: dict[str, str] = {}
        for symbol in symbols:
            returns = returns_map.get(symbol)
            if not returns:
                assignments[symbol] = "BETA_UNKNOWN"
                continue
            beta = self._beta(returns, benchmark_returns)
            if beta is None:
                assignments[symbol] = "BETA_UNKNOWN"
            elif beta < 0.0:
                assignments[symbol] = "BETA_NEGATIVE"
            elif beta < 0.75:
                assignments[symbol] = "BETA_LOW"
            elif beta < 1.25:
                assignments[symbol] = "BETA_MID"
            else:
                assignments[symbol] = "BETA_HIGH"
        return assignments, factor_weights, factor_regime, basket_symbols

    def _beta(self, asset_returns: list[float], benchmark_returns: list[float]) -> float | None:
        overlap = min(len(asset_returns), len(benchmark_returns), self.settings.portfolio_correlation_lookback_candles)
        if overlap < self.settings.portfolio_correlation_min_overlap:
            return None
        x = asset_returns[-overlap:]
        y = benchmark_returns[-overlap:]
        mean_x = sum(x) / overlap
        mean_y = sum(y) / overlap
        covariance = sum((lhs - mean_x) * (rhs - mean_y) for lhs, rhs in zip(x, y, strict=False)) / overlap
        variance_y = sum((rhs - mean_y) ** 2 for rhs in y) / overlap
        if variance_y <= 0:
            return None
        beta = covariance / variance_y
        if not math.isfinite(beta):
            return None
        return float(beta)

    def _aggregate_group_exposures(self, *, symbol_exposures: dict[str, float], assignments: dict[str, str]) -> dict[str, float]:
        grouped: dict[str, float] = {}
        for symbol, notional in symbol_exposures.items():
            group = assignments.get(symbol)
            if not group:
                continue
            grouped[group] = round(grouped.get(group, 0.0) + float(notional), 8)
        return grouped

    def _factor_attribution(
        self,
        *,
        symbol_exposure_pct: dict[str, float],
        factor_weights: dict[str, float],
    ) -> dict[str, float]:
        raw = {
            symbol: max(float(symbol_exposure_pct.get(symbol, 0.0) or 0.0), 0.0) * max(float(weight), 0.0)
            for symbol, weight in factor_weights.items()
            if symbol in symbol_exposure_pct
        }
        total = sum(raw.values())
        if total <= 0:
            return {}
        return {
            symbol: round(value / total, 8)
            for symbol, value in raw.items()
        }

    def _factor_sleeve_budgets(
        self,
        *,
        factor_attribution: dict[str, float],
        factor_sleeve_performance: dict[str, dict],
    ) -> tuple[dict[str, float], dict[str, float]]:
        sleeves = sorted(set(factor_attribution) | set(factor_sleeve_performance))
        if not sleeves:
            return {}, {}
        quality_scores: dict[str, float] = {}
        for sleeve in sleeves:
            metrics = dict(factor_sleeve_performance.get(sleeve, {}))
            recent_win_rate = float(metrics.get("recent_win_rate", 0.5) or 0.0)
            recent_avg_pnl = float(metrics.get("recent_avg_pnl", 0.0) or 0.0)
            quality_scores[sleeve] = max(
                0.05,
                0.55 * self._clamp01(recent_win_rate)
                + 0.45 * self._clamp01((recent_avg_pnl + 0.02) / 0.04),
            )
        total_quality = sum(quality_scores.values())
        if total_quality <= 0:
            raw_targets = {sleeve: 1.0 / len(sleeves) for sleeve in sleeves}
        else:
            raw_targets = {
                sleeve: quality_scores[sleeve] / total_quality
                for sleeve in sleeves
            }
        targets = self._bounded_share_targets(raw_targets)
        deltas = {
            sleeve: round(
                float(targets.get(sleeve, 0.0)) - float(factor_attribution.get(sleeve, 0.0)),
                8,
            )
            for sleeve in sleeves
        }
        return targets, deltas

    def _bounded_share_targets(self, raw_targets: dict[str, float]) -> dict[str, float]:
        sleeves = list(raw_targets.keys())
        if not sleeves:
            return {}
        count = len(sleeves)
        floor = min(max(float(self.settings.portfolio_factor_sleeve_budget_floor), 0.0), 1.0 / count)
        cap = max(
            floor,
            1.0 / count,
            min(float(self.settings.portfolio_factor_sleeve_budget_cap), 1.0),
        )
        targets = {
            sleeve: min(cap, max(floor, float(raw_targets.get(sleeve, 0.0))))
            for sleeve in sleeves
        }
        for _ in range(count * 4):
            total = sum(targets.values())
            gap = 1.0 - total
            if abs(gap) <= 1e-8:
                break
            if gap > 0:
                adjustable = [
                    sleeve for sleeve in sleeves
                    if targets[sleeve] < cap - 1e-8
                ]
                if not adjustable:
                    break
                weights = {
                    sleeve: max(float(raw_targets.get(sleeve, 0.0)), 1e-6)
                    for sleeve in adjustable
                }
                weight_total = sum(weights.values())
                for sleeve in adjustable:
                    headroom = cap - targets[sleeve]
                    increment = gap * (weights[sleeve] / max(weight_total, 1e-8))
                    targets[sleeve] += min(headroom, increment)
            else:
                adjustable = [
                    sleeve for sleeve in sleeves
                    if targets[sleeve] > floor + 1e-8
                ]
                if not adjustable:
                    break
                weights = {
                    sleeve: max(targets[sleeve] - floor, 1e-6)
                    for sleeve in adjustable
                }
                weight_total = sum(weights.values())
                for sleeve in adjustable:
                    slack = targets[sleeve] - floor
                    decrement = (-gap) * (weights[sleeve] / max(weight_total, 1e-8))
                    targets[sleeve] -= min(slack, decrement)
        total = sum(targets.values())
        if total <= 0:
            equal_weight = round(1.0 / count, 8)
            return {sleeve: equal_weight for sleeve in sleeves}
        normalized = {
            sleeve: float(value) / total
            for sleeve, value in targets.items()
        }
        return {
            sleeve: round(normalized[sleeve], 8)
            for sleeve in sleeves
        }

    def _clamp01(self, value: float) -> float:
        return max(0.0, min(float(value), 1.0))

    def _budget_gap_summary(self, deltas: dict[str, float]) -> tuple[float, str | None, str | None]:
        if not deltas:
            return 0.0, None, None
        dominant_over_budget_sleeve = min(deltas, key=lambda sleeve: float(deltas.get(sleeve, 0.0)))
        dominant_under_budget_sleeve = max(deltas, key=lambda sleeve: float(deltas.get(sleeve, 0.0)))
        max_gap = max(abs(float(value)) for value in deltas.values())
        return (
            round(max_gap, 8),
            dominant_over_budget_sleeve if float(deltas.get(dominant_over_budget_sleeve, 0.0)) < 0.0 else None,
            dominant_under_budget_sleeve if float(deltas.get(dominant_under_budget_sleeve, 0.0)) > 0.0 else None,
        )

    def _factor_basket_symbols(
        self,
        *,
        symbol_exposures: dict[str, float] | None = None,
        candidate_symbol: str | None = None,
        symbols_for_analysis: list[str] | None = None,
    ) -> list[str]:
        default_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        if not self.settings.portfolio_factor_basket_json:
            configured_symbols = default_symbols
        else:
            try:
                payload = json.loads(self.settings.portfolio_factor_basket_json)
            except json.JSONDecodeError:
                payload = default_symbols
            if not isinstance(payload, list):
                payload = default_symbols
            configured_symbols = [str(symbol).upper() for symbol in payload if str(symbol).strip()] or default_symbols

        adaptive_symbols: list[str] = list(configured_symbols)
        ranked_active_symbols = sorted(
            (symbol_exposures or {}).items(),
            key=lambda item: float(item[1]),
            reverse=True,
        )
        for symbol, _ in ranked_active_symbols[: max(int(self.settings.portfolio_factor_active_symbol_limit), 0)]:
            adaptive_symbols.append(str(symbol).upper())
        if symbols_for_analysis:
            adaptive_symbols.extend(str(symbol).upper() for symbol in symbols_for_analysis if str(symbol).strip())
        if candidate_symbol:
            adaptive_symbols.append(str(candidate_symbol).upper())

        deduped: list[str] = []
        for symbol in adaptive_symbols:
            normalized = str(symbol).upper().strip()
            if not normalized or normalized in deduped:
                continue
            deduped.append(normalized)
        return deduped or default_symbols

    def _market_factor_profile(self, returns_map: dict[str, list[float]]) -> tuple[list[float], dict[str, float], str]:
        aligned_map = {
            symbol: series
            for symbol, series in returns_map.items()
            if series
        }
        if not aligned_map:
            return [], {}, "RANGING"
        overlap = min(len(series) for series in aligned_map.values())
        if overlap < self.settings.portfolio_correlation_min_overlap:
            return [], {}, "RANGING"
        aligned_map = {
            symbol: series[-overlap:]
            for symbol, series in aligned_map.items()
        }
        symbols = sorted(aligned_map.keys())
        if len(symbols) == 1:
            symbol = symbols[0]
            return aligned_map[symbol], {symbol: 1.0}, "RANGING"

        covariance_matrix = self._covariance_matrix([aligned_map[symbol] for symbol in symbols], overlap)
        principal_component = self._principal_component(covariance_matrix)
        if not principal_component:
            factor_weights = {symbol: round(1.0 / len(symbols), 8) for symbol in symbols}
        else:
            loadings = [abs(value) for value in principal_component]
            total_loading = sum(loadings)
            if total_loading <= 0:
                factor_weights = {symbol: round(1.0 / len(symbols), 8) for symbol in symbols}
            else:
                raw_weights = {
                    symbol: loadings[index] / total_loading
                    for index, symbol in enumerate(symbols)
                }
                factor_regime = self._factor_regime(aligned_map)
                factor_weights = self._regime_adjusted_factor_weights(
                    raw_weights=raw_weights,
                    aligned_map=aligned_map,
                    regime=factor_regime,
                )
                weighted_returns = [
                    sum(factor_weights[symbol] * aligned_map[symbol][index] for symbol in symbols)
                    for index in range(overlap)
                ]
                return weighted_returns, factor_weights, factor_regime
        factor_regime = self._factor_regime(aligned_map)
        weighted_returns = [
            sum(factor_weights[symbol] * aligned_map[symbol][index] for symbol in symbols)
            for index in range(overlap)
        ]
        return weighted_returns, factor_weights, factor_regime

    def _factor_regime(self, aligned_map: dict[str, list[float]]) -> str:
        symbols = sorted(aligned_map.keys())
        if not symbols:
            return "RANGING"
        overlap = min(len(series) for series in aligned_map.values())
        aggregate = [
            sum(aligned_map[symbol][index] for symbol in symbols) / len(symbols)
            for index in range(overlap)
        ]
        mean_return = sum(aggregate) / max(overlap, 1)
        variance = sum((value - mean_return) ** 2 for value in aggregate) / max(overlap, 1)
        volatility = math.sqrt(max(variance, 0.0))
        directional_strength = abs(mean_return)
        if volatility >= self.settings.regime_high_vol_skip_volatility:
            return "HIGH_VOL"
        if directional_strength >= max(volatility * 0.35, 0.0025):
            return "TRENDING"
        return "RANGING"

    def _regime_adjusted_factor_weights(
        self,
        *,
        raw_weights: dict[str, float],
        aligned_map: dict[str, list[float]],
        regime: str,
    ) -> dict[str, float]:
        symbols = sorted(raw_weights.keys())
        if not symbols:
            return {}
        equal_weight = 1.0 / len(symbols)
        adjusted: dict[str, float] = {}
        for symbol in symbols:
            base_weight = float(raw_weights[symbol])
            series = aligned_map[symbol]
            mean_value = sum(series) / max(len(series), 1)
            variance = sum((value - mean_value) ** 2 for value in series) / max(len(series), 1)
            volatility = math.sqrt(max(variance, 0.0))
            if regime == "TRENDING":
                adjusted[symbol] = max(base_weight, 0.0) ** 1.35
            elif regime == "HIGH_VOL":
                adjusted[symbol] = max(base_weight, 0.0) / max(volatility, 1e-6)
            else:
                adjusted[symbol] = (base_weight * 0.6) + (equal_weight * 0.4)
        total = sum(adjusted.values())
        if total <= 0:
            return {symbol: round(equal_weight, 8) for symbol in symbols}
        return {
            symbol: round(adjusted[symbol] / total, 8)
            for symbol in symbols
        }

    def _covariance_matrix(self, series_list: list[list[float]], overlap: int) -> list[list[float]]:
        means = [sum(series) / overlap for series in series_list]
        matrix: list[list[float]] = []
        for left_index, left_series in enumerate(series_list):
            row: list[float] = []
            for right_index, right_series in enumerate(series_list):
                covariance = sum(
                    (left_series[position] - means[left_index]) * (right_series[position] - means[right_index])
                    for position in range(overlap)
                ) / max(overlap, 1)
                row.append(float(covariance))
            matrix.append(row)
        return matrix

    def _principal_component(self, covariance_matrix: list[list[float]]) -> list[float]:
        dimension = len(covariance_matrix)
        if dimension == 0:
            return []
        vector = [1.0 / dimension for _ in range(dimension)]
        for _ in range(32):
            next_vector = [
                sum(covariance_matrix[row][column] * vector[column] for column in range(dimension))
                for row in range(dimension)
            ]
            norm = math.sqrt(sum(value * value for value in next_vector))
            if norm <= 0:
                return []
            vector = [value / norm for value in next_vector]
        return vector

    def _concentration_drift(self, profile: dict, previous: dict) -> dict[str, float]:
        if not previous:
            return {
                "gross_exposure_drift": 0.0,
                "cluster_concentration_drift": 0.0,
                "beta_bucket_concentration_drift": 0.0,
                "cluster_turnover": 0.0,
                "factor_sleeve_budget_turnover": 0.0,
            }
        previous_clusters = previous.get("cluster_assignments") or {}
        current_clusters = profile.get("cluster_assignments") or {}
        comparable_symbols = set(previous_clusters) & set(current_clusters)
        turnover = 0.0
        if comparable_symbols:
            changed = sum(
                1
                for symbol in comparable_symbols
                if previous_clusters.get(symbol) != current_clusters.get(symbol)
            )
            turnover = changed / max(len(comparable_symbols), 1)
        previous_budgets = previous.get("factor_sleeve_budget_targets") or {}
        current_budgets = profile.get("factor_sleeve_budget_targets") or {}
        budget_sleeves = set(previous_budgets) | set(current_budgets)
        budget_turnover = 0.0
        if budget_sleeves:
            budget_turnover = 0.5 * sum(
                abs(float(current_budgets.get(sleeve, 0.0)) - float(previous_budgets.get(sleeve, 0.0)))
                for sleeve in budget_sleeves
            )
        return {
            "gross_exposure_drift": round(
                float(profile.get("gross_exposure_pct", 0.0)) - float(previous.get("gross_exposure_pct", 0.0)),
                8,
            ),
            "cluster_concentration_drift": round(
                max((float(value) for value in profile.get("cluster_exposure_pct", {}).values()), default=0.0)
                - max((float(value) for value in previous.get("cluster_exposure_pct", {}).values()), default=0.0),
                8,
            ),
            "beta_bucket_concentration_drift": round(
                max((float(value) for value in profile.get("beta_bucket_exposure_pct", {}).values()), default=0.0)
                - max((float(value) for value in previous.get("beta_bucket_exposure_pct", {}).values()), default=0.0),
                8,
            ),
            "cluster_turnover": round(turnover, 8),
            "factor_sleeve_budget_turnover": round(budget_turnover, 8),
        }

    def _persist_concentration_profile(self, user_id: str, profile: dict) -> None:
        snapshot = dict(profile)
        snapshot.setdefault("updated_at", datetime.now(timezone.utc).isoformat())
        self.cache.set_json(
            self._concentration_profile_key(user_id),
            snapshot,
            ttl=self.settings.monitor_state_ttl_seconds,
        )
        history_key = self._concentration_history_key(user_id)
        bucket = self.cache.get_json(history_key) or {"snapshots": []}
        keep = max(int(self.settings.portfolio_concentration_history_limit), 1)
        snapshots = list(bucket.get("snapshots", []))[-(keep - 1) :]
        snapshots.append(snapshot)
        self.cache.set_json(
            history_key,
            {"snapshots": snapshots},
            ttl=self.settings.monitor_state_ttl_seconds,
        )
        factor_history_key = self._factor_history_key(user_id)
        factor_bucket = self.cache.get_json(factor_history_key) or {"snapshots": []}
        factor_keep = max(int(self.settings.portfolio_factor_history_limit), 1)
        factor_snapshots = list(factor_bucket.get("snapshots", []))[-(factor_keep - 1) :]
        factor_snapshots.append(
            {
                "updated_at": snapshot.get("updated_at"),
                "factor_universe_symbols": list(snapshot.get("factor_universe_symbols") or []),
                "factor_weights": dict(snapshot.get("factor_weights") or {}),
                "factor_attribution": dict(snapshot.get("factor_attribution") or {}),
                "factor_sleeve_budget_targets": dict(snapshot.get("factor_sleeve_budget_targets") or {}),
                "factor_sleeve_budget_deltas": dict(snapshot.get("factor_sleeve_budget_deltas") or {}),
                "factor_sleeve_budget_turnover": float(snapshot.get("factor_sleeve_budget_turnover", 0.0) or 0.0),
                "max_factor_sleeve_budget_gap_pct": float(snapshot.get("max_factor_sleeve_budget_gap_pct", 0.0) or 0.0),
                "dominant_over_budget_sleeve": snapshot.get("dominant_over_budget_sleeve"),
                "dominant_under_budget_sleeve": snapshot.get("dominant_under_budget_sleeve"),
                "dominant_factor_sleeve": snapshot.get("dominant_factor_sleeve"),
                "factor_regime": snapshot.get("factor_regime"),
                "factor_model": snapshot.get("factor_model"),
            }
        )
        self.cache.set_json(
            factor_history_key,
            {"snapshots": factor_snapshots},
            ttl=self.settings.monitor_state_ttl_seconds,
        )
        if self.firestore is not None and hasattr(self.firestore, "save_portfolio_concentration_snapshot"):
            try:
                self.firestore.save_portfolio_concentration_snapshot(user_id, snapshot)
            except RuntimeError:
                pass
        if self.firestore is not None and hasattr(self.firestore, "save_factor_attribution_snapshot"):
            try:
                self.firestore.save_factor_attribution_snapshot(
                    user_id,
                    {
                        "updated_at": snapshot.get("updated_at"),
                        "factor_universe_symbols": list(snapshot.get("factor_universe_symbols") or []),
                        "factor_weights": dict(snapshot.get("factor_weights") or {}),
                        "factor_attribution": dict(snapshot.get("factor_attribution") or {}),
                        "factor_sleeve_budget_targets": dict(snapshot.get("factor_sleeve_budget_targets") or {}),
                        "factor_sleeve_budget_deltas": dict(snapshot.get("factor_sleeve_budget_deltas") or {}),
                        "factor_sleeve_budget_turnover": float(snapshot.get("factor_sleeve_budget_turnover", 0.0) or 0.0),
                        "max_factor_sleeve_budget_gap_pct": float(snapshot.get("max_factor_sleeve_budget_gap_pct", 0.0) or 0.0),
                        "dominant_over_budget_sleeve": snapshot.get("dominant_over_budget_sleeve"),
                        "dominant_under_budget_sleeve": snapshot.get("dominant_under_budget_sleeve"),
                        "dominant_factor_sleeve": snapshot.get("dominant_factor_sleeve"),
                        "factor_regime": snapshot.get("factor_regime"),
                        "factor_model": snapshot.get("factor_model"),
                    },
                )
            except RuntimeError:
                pass

    def _record_factor_sleeve_outcome(self, *, user_id: str, symbol: str, pnl: float) -> None:
        sleeve = self._factor_sleeve_for_symbol(user_id=user_id, symbol=symbol)
        history_key = self._factor_performance_key(user_id)
        bucket = self.cache.get_json(history_key) or {"sleeves": {}}
        sleeves = dict(bucket.get("sleeves", {}))
        sleeve_payload = dict(sleeves.get(sleeve, {}))
        sleeve_payload["realized_pnl"] = round(float(sleeve_payload.get("realized_pnl", 0.0)) + float(pnl), 8)
        sleeve_payload["wins"] = int(sleeve_payload.get("wins", 0)) + int(pnl > 0)
        sleeve_payload["losses"] = int(sleeve_payload.get("losses", 0)) + int(pnl < 0)
        sleeve_payload["closed_trades"] = int(sleeve_payload.get("closed_trades", 0)) + 1
        recent_events = self._append_recent_sleeve_event(
            user_id=user_id,
            sleeve=sleeve,
            pnl=pnl,
        )
        sleeve_payload.update(self._recent_sleeve_summary(recent_events))
        sleeve_payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        sleeves[sleeve] = sleeve_payload
        self.cache.set_json(
            history_key,
            {"sleeves": sleeves},
            ttl=self.settings.monitor_state_ttl_seconds,
        )
        if self.firestore is not None and hasattr(self.firestore, "save_factor_sleeve_performance"):
            self.firestore.save_factor_sleeve_performance(user_id, {"sleeves": sleeves})

    def _factor_sleeve_for_symbol(self, *, user_id: str, symbol: str) -> str:
        normalized = str(symbol or "").upper().strip()
        if not normalized:
            return "UNASSIGNED"
        profile = self.latest_concentration_profile(user_id)
        factor_attribution = profile.get("factor_attribution") or {}
        if normalized in factor_attribution:
            return normalized
        dominant = str(profile.get("dominant_factor_sleeve") or "").upper().strip()
        if dominant:
            return dominant
        return normalized

    def _append_recent_sleeve_event(self, *, user_id: str, sleeve: str, pnl: float) -> list[dict]:
        history_key = self._factor_performance_window_key(user_id)
        bucket = self.cache.get_json(history_key) or {"sleeves": {}}
        sleeves = dict(bucket.get("sleeves", {}))
        window = list(sleeves.get(sleeve, []))
        keep = max(int(self.settings.portfolio_factor_performance_window_trades), 1)
        window = window[-(keep - 1) :]
        window.append(
            {
                "pnl": round(float(pnl), 8),
                "won": bool(pnl > 0),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        sleeves[sleeve] = window
        self.cache.set_json(
            history_key,
            {"sleeves": sleeves},
            ttl=self.settings.monitor_state_ttl_seconds,
        )
        return window

    def _recent_sleeve_summary(self, events: list[dict]) -> dict[str, float | int]:
        if not events:
            return {
                "recent_realized_pnl": 0.0,
                "recent_wins": 0,
                "recent_losses": 0,
                "recent_closed_trades": 0,
                "recent_win_rate": 0.0,
                "recent_avg_pnl": 0.0,
            }
        realized_pnl = sum(float(event.get("pnl", 0.0) or 0.0) for event in events)
        wins = sum(int(bool(event.get("won"))) for event in events)
        closed_trades = len(events)
        losses = closed_trades - wins
        return {
            "recent_realized_pnl": round(realized_pnl, 8),
            "recent_wins": wins,
            "recent_losses": losses,
            "recent_closed_trades": closed_trades,
            "recent_win_rate": round(wins / max(closed_trades, 1), 8),
            "recent_avg_pnl": round(realized_pnl / max(closed_trades, 1), 8),
        }

    def _theme_map(self) -> dict[str, set[str]]:
        default_map = {
            "STORE_OF_VALUE": {"BTC"},
            "L1": {"ETH", "SOL", "ADA", "AVAX", "DOT", "ATOM", "NEAR", "SUI", "APT"},
            "DEFI": {"LINK", "UNI", "AAVE", "MKR", "CRV", "SNX", "COMP"},
            "MEME": {"DOGE", "SHIB", "PEPE", "FLOKI", "BONK", "WIF"},
            "AI": {"FET", "AGIX", "OCEAN", "RNDR", "TAO", "WLD"},
            "EXCHANGE": {"BNB", "OKB", "CRO"},
        }
        if not self.settings.portfolio_theme_map_json:
            return default_map
        try:
            payload = json.loads(self.settings.portfolio_theme_map_json)
        except json.JSONDecodeError:
            return default_map
        resolved: dict[str, set[str]] = {}
        for theme, assets in payload.items():
            if not isinstance(assets, list):
                continue
            resolved[str(theme).upper()] = {str(asset).upper() for asset in assets}
        return resolved or default_map

    def _base_asset(self, symbol: str) -> str:
        for suffix in ("USDT", "USDC", "BUSD", "FDUSD", "BTC", "ETH"):
            if symbol.endswith(suffix) and len(symbol) > len(suffix):
                return symbol[: -len(suffix)]
        return symbol

