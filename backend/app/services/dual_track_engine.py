from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from app.core.config import Settings
from app.schemas.trading import TradeRequest


@dataclass(frozen=True)
class SniperDecision:
    symbol: str
    action: str
    confidence: float
    strategy: str
    requested_notional: float
    reason: str
    market_bias: dict
    snapshot: dict


@dataclass
class DualTrackCoordinator:
    settings: Settings
    cache: any
    market_data: any
    feature_pipeline: any
    sentiment_engine: any
    whale_tracker: any
    liquidity_monitor: any
    multi_chain_router: any
    drawdown_protection: any
    narrative_macro_intelligence: any

    async def sniper_decision(
        self,
        *,
        user_id: str,
        symbol: str,
        account_equity: float | None = None,
    ) -> SniperDecision:
        symbol = symbol.upper()
        market_bias = self._load_bias(symbol)
        warmup = self.cache.get_json(f"warmup:{user_id}:{symbol}") or {}
        frames, order_book = await asyncio.gather(
            self.market_data.fetch_multi_timeframe_ohlcv(symbol, intervals=("1m", "5m", "15m")),
            self.market_data.fetch_order_book(symbol),
        )
        snapshot = self.feature_pipeline.build(symbol, frames, order_book)
        decision = self._apply_sniper_rules(snapshot, market_bias)
        equity = account_equity or self.drawdown_protection.load(user_id).current_equity
        requested_notional = self._notional_from_bias(equity, market_bias, warmup)
        strategy = "SNIPER_TREND" if decision["action"] != "HOLD" else "NO_TRADE"
        reason = (
            f"Fast track {decision['action']} from price/volume/RSI. "
            f"Bias={market_bias['regime']} rsi_1m={snapshot.features.get('1m_rsi', 50):.1f} "
            f"rsi_5m={snapshot.features.get('5m_rsi', 50):.1f} vol_ratio={decision['volume_ratio']:.2f}"
        )
        return SniperDecision(
            symbol=symbol,
            action=decision["action"],
            confidence=decision["confidence"],
            strategy=strategy,
            requested_notional=requested_notional if decision["action"] != "HOLD" else 0.0,
            reason=reason,
            market_bias=market_bias,
            snapshot={
                "price": snapshot.price,
                "regime": snapshot.regime,
                "features": snapshot.features,
            },
        )

    async def build_trade_request(self, *, user_id: str, symbol: str, account_equity: float | None = None) -> TradeRequest | None:
        decision = await self.sniper_decision(user_id=user_id, symbol=symbol, account_equity=account_equity)
        if decision.action == "HOLD" or decision.requested_notional <= 0:
            return None
        return TradeRequest(
            user_id=user_id,
            symbol=decision.symbol,
            side=decision.action,
            order_type="MARKET",
            confidence=decision.confidence,
            reason=decision.reason,
            requested_notional=decision.requested_notional,
            feature_snapshot=decision.snapshot["features"],
            strategy=decision.strategy,
            macro_bias_multiplier=decision.market_bias["multiplier"],
            macro_bias_regime=decision.market_bias["regime"],
        )

    async def refresh_brain_bias(self, symbol: str) -> dict:
        symbol = symbol.upper()
        macro_task = asyncio.create_task(
            self.narrative_macro_intelligence.fetch_macro_context()
        )
        frames_task = asyncio.create_task(
            self.market_data.fetch_multi_timeframe_ohlcv(symbol, intervals=("1m", "5m", "15m"))
        )
        order_book_task = asyncio.create_task(self.market_data.fetch_order_book(symbol))
        macro_context, frames, order_book = await asyncio.gather(macro_task, frames_task, order_book_task)
        snapshot = self.feature_pipeline.build(symbol, frames, order_book)
        chain_route = self.multi_chain_router.route(symbol, "BUY", 0.0)
        sentiment_task = asyncio.create_task(self.sentiment_engine.analyze_token(symbol, snapshot.features))
        whale_task = asyncio.create_task(self.whale_tracker.evaluate_token(symbol, chain_route["chain"], snapshot.features))
        liquidity_task = asyncio.create_task(self.liquidity_monitor.assess_token(symbol, chain_route["chain"], snapshot.features))
        sentiment, whale, liquidity = await asyncio.gather(sentiment_task, whale_task, liquidity_task)
        social_metrics = {
            "hype_score": float(sentiment.get("hype_score", 0.0)),
            "velocity_score": min(1.0, float(sentiment.get("buzz_score", 0.0)) + abs(snapshot.features.get("1m_return", 0.0)) * 12),
            "dispersion_score": 1.0 - min(1.0, float(sentiment.get("volume_alignment", 0.0))),
            "influencer_concentration": min(1.0, float(sentiment.get("buzz_score", 0.0)) * 0.8 + 0.15),
            "hype_mean": 0.55,
            "hype_std": 0.14,
        }
        onchain_metrics = {
            "buy_volume_score": min(1.0, snapshot.features.get("15m_volume", 0.0) / 2_500_000),
            "buy_volume_trend": snapshot.features.get("5m_return", 0.0) - snapshot.features.get("15m_return", 0.0),
            "whale_participation": float(whale.get("score", 0.0)),
            "exchange_inflow_risk": min(1.0, 1.0 - float(liquidity.get("liquidity_stability", 1.0))),
            "stablecoin_support": max(0.0, 1.0 - float(liquidity.get("rug_pull_risk", 0.0))),
        }
        report = await self.narrative_macro_intelligence.analyze_market(
            symbol=symbol,
            social_metrics=social_metrics,
            onchain_metrics=onchain_metrics,
            macro_metrics=macro_context["macro_metrics"],
        )
        bias = {
            **report["macro_bias"],
            "symbol": symbol,
            "sentiment_hype_score": social_metrics["hype_score"],
            "whale_score": whale.get("score", 0.0),
            "liquidity_stability": liquidity.get("liquidity_stability", 1.0),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.cache.set_json(
            f"dual_track:bias:{symbol}",
            bias,
            ttl=self.settings.dual_track_bias_ttl_seconds,
        )
        return bias

    async def warmup_execution_context(self, *, user_id: str, symbol: str) -> dict:
        symbol = symbol.upper()
        drawdown = self.drawdown_protection.load(user_id)
        market_bias = self._load_bias(symbol)
        latest_price_task = asyncio.create_task(self.market_data.fetch_latest_price(symbol))
        order_book_task = asyncio.create_task(self.market_data.fetch_order_book(symbol))
        latest_price, order_book = await asyncio.gather(latest_price_task, order_book_task)
        payload = {
            "user_id": user_id,
            "symbol": symbol,
            "bias_regime": market_bias["regime"],
            "bias_multiplier": market_bias["multiplier"],
            "equity": drawdown.current_equity,
            "active_trades": len([key for key in self.cache.keys("active_trade:*") if user_id in str(self.cache.get_json(key) or {})]),
            "best_bid": float(order_book["bids"][0]["price"]) if order_book.get("bids") else latest_price,
            "best_ask": float(order_book["asks"][0]["price"]) if order_book.get("asks") else latest_price,
            "latest_price": latest_price,
            "warmed_at": datetime.now(timezone.utc).isoformat(),
        }
        self.cache.set_json(
            f"warmup:{user_id}:{symbol}",
            payload,
            ttl=self.settings.dual_track_warmup_ttl_seconds,
        )
        return payload

    async def run_brain_loop(self, symbol: str) -> None:
        symbol = symbol.upper()
        while True:
            try:
                await self.refresh_brain_bias(symbol)
            except Exception as exc:
                self.cache.set_json(
                    f"dual_track:error:{symbol}",
                    {"symbol": symbol, "error": str(exc), "updated_at": datetime.now(timezone.utc).isoformat()},
                    ttl=self.settings.monitor_state_ttl_seconds,
                )
            await asyncio.sleep(self.settings.dual_track_brain_poll_seconds)

    def _load_bias(self, symbol: str) -> dict:
        symbol_bias = self.cache.get_json(f"dual_track:bias:{symbol.upper()}") or {}
        macro_bias = self.cache.get_json("macro:global_bias") or {}
        regime = str(symbol_bias.get("regime") or macro_bias.get("regime") or "NEUTRAL").upper()
        multiplier = float(symbol_bias.get("multiplier") or macro_bias.get("multiplier") or 1.0)
        return {
            "regime": regime,
            "multiplier": multiplier,
            "reason": str(symbol_bias.get("reason") or macro_bias.get("reason") or "No deep-track bias yet."),
            "updated_at": symbol_bias.get("updated_at") or macro_bias.get("updated_at"),
        }

    def _apply_sniper_rules(self, snapshot, market_bias: dict) -> dict:
        thresholds = self._sniper_thresholds(snapshot.symbol)
        rsi_1m = float(snapshot.features.get("1m_rsi", 50.0))
        rsi_5m = float(snapshot.features.get("5m_rsi", 50.0))
        volume_5m = float(snapshot.features.get("5m_volume", 0.0))
        volume_15m = max(float(snapshot.features.get("15m_volume", 0.0)), 1e-8)
        volume_ratio = volume_5m / volume_15m
        price_momentum = snapshot.features.get("1m_return", 0.0) + snapshot.features.get("5m_return", 0.0)
        bullish = (
            rsi_1m >= thresholds["long_entry_rsi"]
            and rsi_5m >= thresholds["long_confirmation_rsi"]
            and volume_ratio >= 0.28
            and price_momentum > 0
            and snapshot.order_book_imbalance > -0.10
            and market_bias["regime"] != "BEARISH"
        )
        bearish = (
            rsi_1m <= thresholds["short_entry_rsi"]
            and rsi_5m <= thresholds["short_confirmation_rsi"]
            and volume_ratio >= 0.28
            and price_momentum < 0
            and snapshot.order_book_imbalance < 0.10
        )
        if bullish:
            confidence = min(0.95, 0.55 + max(0.0, price_momentum) * 12 + min(volume_ratio, 1.0) * 0.10)
            return {"action": "BUY", "confidence": round(confidence, 4), "volume_ratio": volume_ratio, "thresholds": thresholds}
        if bearish:
            confidence = min(0.95, 0.55 + max(0.0, -price_momentum) * 12 + min(volume_ratio, 1.0) * 0.10)
            return {"action": "SELL", "confidence": round(confidence, 4), "volume_ratio": volume_ratio, "thresholds": thresholds}
        return {"action": "HOLD", "confidence": 0.0, "volume_ratio": volume_ratio, "thresholds": thresholds}

    def _notional_from_bias(self, equity: float, market_bias: dict, warmup: dict) -> float:
        base_fraction = 0.015 if market_bias["regime"] in {"BULLISH", "BEARISH"} else 0.01
        warmed_multiplier = 1.05 if warmup else 1.0
        return round(max(self.settings.exchange_min_notional, equity * base_fraction * market_bias["multiplier"] * warmed_multiplier), 6)

    def _sniper_thresholds(self, symbol: str) -> dict:
        overrides = self.cache.get_json(f"dual_track:thresholds:{symbol.upper()}") or {}
        return {
            "long_entry_rsi": float(overrides.get("long_entry_rsi", self.settings.dual_track_sniper_min_rsi)),
            "long_confirmation_rsi": float(overrides.get("long_confirmation_rsi", 50.0)),
            "short_entry_rsi": float(overrides.get("short_entry_rsi", self.settings.dual_track_sniper_max_rsi)),
            "short_confirmation_rsi": float(overrides.get("short_confirmation_rsi", 50.0)),
        }

