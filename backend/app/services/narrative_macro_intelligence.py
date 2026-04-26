from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from app.core.config import Settings

if TYPE_CHECKING:
    from app.services.firestore_repo import FirestoreRepository
    from app.services.redis_state_manager import RedisStateManager

try:
    import yfinance as yf
except ModuleNotFoundError:
    yf = None

try:
    from pinecone.grpc import PineconeGRPC as Pinecone
    from pinecone import ServerlessSpec
except ModuleNotFoundError:
    Pinecone = None
    ServerlessSpec = None


MACRO_TICKERS = {
    "dxy": "DX-Y.NYB",
    "spx": "SPY",
    "nasdaq": "QQQ",
    "gold": "GC=F",
    "us10y": "^TNX",
    "btc": "BTC-USD",
}


@dataclass(frozen=True)
class HistoricalBlackSwanEvent:
    event_id: str
    name: str
    event_date: str
    narrative: str
    keywords: tuple[str, ...]
    stress_signature: dict[str, float]


@dataclass(frozen=True)
class HistoricalMatch:
    event_id: str
    name: str
    similarity: float
    stress_signature: dict[str, float]


@dataclass(frozen=True)
class LeadLagInsight:
    lead_asset: str
    lag_asset: str
    lead_move_threshold: float
    lag_window_minutes: int
    probability: float
    sample_size: int
    matched_records: int


@dataclass
class StopTighteningAction:
    trade_id: str
    user_id: str
    symbol: str
    side: str
    old_trailing_stop_pct: float
    new_trailing_stop_pct: float
    old_stop_loss: float
    new_stop_loss: float


@dataclass
class NarrativeMacroIntelligenceEngine:
    settings: Settings
    redis_state_manager: RedisStateManager
    firestore: FirestoreRepository | None = None
    vector_dimension: int = 48

    def __post_init__(self) -> None:
        self.artifact_dir = Path(self.settings.model_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir = self.artifact_dir / "macro_intelligence"
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.archive_path = self.report_dir / "lead_lag_archive.jsonl"
        self.event_catalog = self._seed_events()
        self.cache = self.redis_state_manager.cache

    async def analyze_market(
        self,
        *,
        symbol: str,
        social_metrics: dict[str, float],
        onchain_metrics: dict[str, float],
        macro_metrics: dict[str, float] | None = None,
    ) -> dict:
        macro_context = await self.fetch_macro_context()
        combined_macro = {**macro_context["macro_metrics"], **(macro_metrics or {})}
        current_pattern = self._build_market_pattern(symbol, social_metrics, onchain_metrics, combined_macro)
        historical_matches = await self._match_black_swan_patterns(current_pattern)
        await self._resolve_pending_lead_lag_events(macro_context)
        await self._stage_pending_lead_lag_events(macro_context)
        lead_lag = await self.query_lead_lag_pattern(
            lead_asset="nasdaq",
            lag_asset="btc",
            lead_move_threshold=-0.015,
            lag_window_minutes=30,
            query_context=current_pattern,
        )
        divergence = self._calculate_divergence_score(social_metrics, onchain_metrics, combined_macro)
        bubble_risk = self._bubble_risk(divergence, historical_matches, lead_lag, combined_macro)
        tightening_actions: list[StopTighteningAction] = []
        if bubble_risk["signal"]:
            tightening_actions = self._tighten_trailing_stops(
                bubble_risk_score=bubble_risk["bubble_risk_score"],
                reason=bubble_risk["reason"],
            )
        macro_bias = self._macro_bias_payload(combined_macro, bubble_risk, lead_lag)
        self._store_global_bias(macro_bias)
        report = {
            "symbol": symbol,
            "as_of": datetime.now(timezone.utc).isoformat(),
            "market_pattern": current_pattern,
            "macro_snapshot": macro_context,
            "historical_matches": [asdict(match) for match in historical_matches],
            "lead_lag_insight": asdict(lead_lag),
            "divergence_score": divergence,
            "bubble_risk": {
                **bubble_risk,
                "active_trade_adjustments": [asdict(action) for action in tightening_actions],
            },
            "macro_bias": macro_bias,
            "game_theory": self._game_theory_explanation(divergence, macro_bias, lead_lag),
        }
        self._persist_report(symbol, report)
        return report

    async def fetch_macro_context(self) -> dict:
        tasks = {
            alias: asyncio.create_task(self._fetch_series(alias, ticker))
            for alias, ticker in MACRO_TICKERS.items()
        }
        frames: dict[str, pd.DataFrame] = {}
        errors: dict[str, str] = {}
        for alias, task in tasks.items():
            try:
                frames[alias] = await task
            except Exception as exc:
                cached = self.cache.get_json(f"macro:series:{alias}") or {}
                if cached.get("rows"):
                    frames[alias] = pd.DataFrame(cached["rows"])
                else:
                    frames[alias] = pd.DataFrame(columns=["Close", "Volume"])
                    errors[alias] = str(exc)
        metrics = self._compute_macro_metrics(frames)
        snapshot = {
            "as_of": datetime.now(timezone.utc).isoformat(),
            "macro_metrics": metrics,
            "errors": errors,
        }
        self.cache.set_json("macro:latest_snapshot", snapshot, ttl=self.settings.monitor_state_ttl_seconds)
        return snapshot

    async def run_macro_worker(self, symbol: str = "BTCUSDT", poll_seconds: int = 300) -> None:
        while True:
            try:
                social = self.cache.get_json(f"macro:social:{symbol}") or {}
                onchain = self.cache.get_json(f"macro:onchain:{symbol}") or {}
                await self.analyze_market(
                    symbol=symbol,
                    social_metrics=social,
                    onchain_metrics=onchain,
                    macro_metrics=None,
                )
            except Exception as exc:
                self.cache.set_json(
                    "macro:worker:error",
                    {"error": str(exc), "updated_at": datetime.now(timezone.utc).isoformat()},
                    ttl=self.settings.monitor_state_ttl_seconds,
                )
            await asyncio.sleep(poll_seconds)

    async def query_lead_lag_pattern(
        self,
        *,
        lead_asset: str,
        lag_asset: str,
        lead_move_threshold: float,
        lag_window_minutes: int,
        query_context: dict[str, Any],
    ) -> LeadLagInsight:
        query_payload = {
            "lead_asset": lead_asset,
            "lag_asset": lag_asset,
            "lead_move_threshold": lead_move_threshold,
            "lag_window_minutes": lag_window_minutes,
            "query_context": query_context,
        }
        vector = self._embed(json.dumps(query_payload, sort_keys=True))
        matches = await self._query_pinecone(
            vector=vector,
            filter_={
                "asset_class": {"$eq": "macro"},
                "event_type": {"$eq": f"{lead_asset}_leadlag"},
                "time_relevance": {"$eq": f"1h_to_{lag_window_minutes}m"},
                "lag_asset": {"$eq": lag_asset},
            },
            top_k=32,
        )
        if not matches:
            matches = self._query_local_lead_lag(lead_asset, lag_asset, lag_window_minutes)
        probability = float(np.mean([float(item["metadata"].get("lag_dump_outcome", 0.0)) for item in matches])) if matches else 0.0
        return LeadLagInsight(
            lead_asset=lead_asset,
            lag_asset=lag_asset,
            lead_move_threshold=lead_move_threshold,
            lag_window_minutes=lag_window_minutes,
            probability=round(probability, 6),
            sample_size=len(matches),
            matched_records=len(matches),
        )

    def load_global_bias(self) -> dict:
        return self.cache.get_json("macro:global_bias") or {
            "regime": "NEUTRAL",
            "multiplier": 1.0,
            "reason": "No macro worker signal available.",
            "updated_at": None,
        }

    def _build_market_pattern(
        self,
        symbol: str,
        social_metrics: dict[str, float],
        onchain_metrics: dict[str, float],
        macro_metrics: dict[str, float],
    ) -> dict:
        return {
            "symbol": symbol,
            "social_hype_score": round(self._bounded(social_metrics.get("hype_score", 0.0)), 6),
            "social_velocity": round(self._bounded(social_metrics.get("velocity_score", 0.0)), 6),
            "sentiment_dispersion": round(self._bounded(social_metrics.get("dispersion_score", 0.0)), 6),
            "onchain_buy_volume_score": round(self._bounded(onchain_metrics.get("buy_volume_score", 0.0)), 6),
            "onchain_buy_volume_trend": round(float(onchain_metrics.get("buy_volume_trend", 0.0)), 6),
            "exchange_inflow_risk": round(self._bounded(onchain_metrics.get("exchange_inflow_risk", 0.0)), 6),
            "stablecoin_support": round(self._bounded(onchain_metrics.get("stablecoin_support", 0.0)), 6),
            "dxy_1h_return": round(float(macro_metrics.get("dxy_1h_return", 0.0)), 6),
            "spx_1h_return": round(float(macro_metrics.get("spx_1h_return", 0.0)), 6),
            "nasdaq_1h_return": round(float(macro_metrics.get("nasdaq_1h_return", 0.0)), 6),
            "gold_1h_return": round(float(macro_metrics.get("gold_1h_return", 0.0)), 6),
            "us10y_1h_change_bps": round(float(macro_metrics.get("us10y_1h_change_bps", 0.0)), 6),
            "safe_haven_rotation": round(self._bounded(macro_metrics.get("safe_haven_rotation", 0.0)), 6),
            "risk_off_spillover": round(self._bounded(macro_metrics.get("risk_off_spillover", 0.0)), 6),
            "inflation_hedge_pressure": round(self._bounded(macro_metrics.get("inflation_hedge_pressure", 0.0)), 6),
            "liquidity_drain_score": round(self._bounded(macro_metrics.get("liquidity_drain_score", 0.0)), 6),
            "macro_bearish_score": round(self._bounded(macro_metrics.get("macro_bearish_score", 0.0)), 6),
        }

    def _calculate_divergence_score(
        self,
        social_metrics: dict[str, float],
        onchain_metrics: dict[str, float],
        macro_metrics: dict[str, float],
    ) -> dict:
        hype = self._bounded(social_metrics.get("hype_score", 0.0))
        velocity = self._bounded(social_metrics.get("velocity_score", 0.0))
        influencer_concentration = self._bounded(social_metrics.get("influencer_concentration", 0.0))
        buy_volume = self._bounded(onchain_metrics.get("buy_volume_score", 0.0))
        buy_volume_trend = float(onchain_metrics.get("buy_volume_trend", 0.0))
        whale_participation = self._bounded(onchain_metrics.get("whale_participation", 0.0))
        hype_mean = float(social_metrics.get("hype_mean", 0.5))
        hype_std = max(float(social_metrics.get("hype_std", 0.1)), 1e-6)
        hype_zscore = float(social_metrics.get("hype_zscore", (hype - hype_mean) / hype_std))
        retail_skew = max(0.0, hype - whale_participation)
        macro_bearish_score = self._bounded(macro_metrics.get("macro_bearish_score", 0.0))
        divergence_score = (
            hype * 0.25
            + velocity * 0.10
            + influencer_concentration * 0.10
            + retail_skew * 0.10
            + max(0.0, -buy_volume_trend) * 0.20
            + macro_bearish_score * 0.20
            + min(1.0, max(0.0, hype_zscore / 3.0)) * 0.15
            - buy_volume * 0.20
        )
        divergence_score = float(max(0.0, min(1.0, divergence_score)))
        bubble_condition = hype >= 0.70 and buy_volume_trend < 0 and buy_volume <= 0.45
        critical_condition = hype_zscore >= 2.0 and macro_bearish_score >= 0.60 and bubble_condition
        return {
            "social_hype_score": round(hype, 6),
            "social_velocity": round(velocity, 6),
            "buy_volume_score": round(buy_volume, 6),
            "buy_volume_trend": round(buy_volume_trend, 6),
            "whale_participation": round(whale_participation, 6),
            "hype_zscore": round(hype_zscore, 6),
            "macro_bearish_score": round(macro_bearish_score, 6),
            "divergence_score": round(divergence_score, 6),
            "bubble_condition": bubble_condition,
            "critical_condition": critical_condition,
        }

    def _bubble_risk(
        self,
        divergence: dict,
        historical_matches: list[HistoricalMatch],
        lead_lag: LeadLagInsight,
        macro_metrics: dict[str, float],
    ) -> dict:
        top_match_similarity = historical_matches[0].similarity if historical_matches else 0.0
        bank_run_similarity = max(
            (match.similarity for match in historical_matches if match.event_id in {"ftx-crash", "luna-collapse"}),
            default=0.0,
        )
        bubble_risk_score = (
            divergence["divergence_score"] * 0.40
            + self._bounded(macro_metrics.get("macro_bearish_score", 0.0)) * 0.20
            + top_match_similarity * 0.15
            + bank_run_similarity * 0.10
            + lead_lag.probability * 0.15
        )
        bubble_risk_score = float(max(0.0, min(1.0, bubble_risk_score)))
        signal = divergence["bubble_condition"] and bubble_risk_score >= 0.60
        severity = "CRITICAL" if divergence["critical_condition"] else "HIGH" if signal else "NORMAL"
        if severity == "CRITICAL":
            bubble_risk_score = max(bubble_risk_score, 0.85)
            signal = True
        reason = (
            "Bubble Risk CRITICAL: hype is 2 sigma above baseline while DXY/risk assets are turning bearish, "
            "a classic reflexivity trap where late longs become the exit liquidity."
            if severity == "CRITICAL"
            else "Bubble Risk triggered because social hype is elevated while on-chain buy volume is deteriorating "
            "and macro cross-asset context is risk-off."
            if signal
            else "No bubble regime detected."
        )
        return {
            "signal": signal,
            "severity": severity,
            "bubble_risk_score": round(bubble_risk_score, 6),
            "reason": reason,
        }

    def _macro_bias_payload(
        self,
        macro_metrics: dict[str, float],
        bubble_risk: dict,
        lead_lag: LeadLagInsight,
    ) -> dict:
        bearish_score = self._bounded(macro_metrics.get("macro_bearish_score", 0.0))
        if bubble_risk["severity"] == "CRITICAL" or bearish_score >= 0.70:
            regime = "BEARISH"
            multiplier = 0.50
        elif bearish_score >= 0.55 or lead_lag.probability >= 0.60:
            regime = "CAUTIOUS"
            multiplier = 0.75
        elif self._bounded(macro_metrics.get("risk_on_spillover", 0.0)) >= 0.60:
            regime = "BULLISH"
            multiplier = 1.10
        else:
            regime = "NEUTRAL"
            multiplier = 1.0
        return {
            "regime": regime,
            "multiplier": round(multiplier, 4),
            "bearish_score": round(bearish_score, 6),
            "lead_lag_probability": round(lead_lag.probability, 6),
            "reason": bubble_risk["reason"] if regime in {"BEARISH", "CAUTIOUS"} else "Macro regime is balanced.",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _match_black_swan_patterns(self, current_pattern: dict) -> list[HistoricalMatch]:
        vector = self._embed(json.dumps(current_pattern, sort_keys=True))
        pinecone_matches = await self._query_pinecone(
            vector=vector,
            filter_={
                "asset_class": {"$eq": "macro"},
                "event_type": {"$eq": "black_swan"},
            },
            top_k=3,
        )
        if pinecone_matches:
            return [
                HistoricalMatch(
                    event_id=str(match["metadata"].get("event_id", "")),
                    name=str(match["metadata"].get("name", "")),
                    similarity=round(float(match["score"]), 6),
                    stress_signature=match["metadata"].get("stress_signature", {}),
                )
                for match in pinecone_matches
            ]
        fallback = []
        for event in self.event_catalog:
            score = self._cosine_similarity(vector, self._event_vector(event))
            fallback.append(
                HistoricalMatch(
                    event_id=event.event_id,
                    name=event.name,
                    similarity=round(score, 6),
                    stress_signature=event.stress_signature,
                )
            )
        return sorted(fallback, key=lambda item: item.similarity, reverse=True)[:3]

    async def _query_pinecone(
        self,
        *,
        vector: np.ndarray,
        filter_: dict | None,
        top_k: int,
    ) -> list[dict]:
        if not self.settings.pinecone_api_key or Pinecone is None or ServerlessSpec is None:
            return []
        try:
            pc = Pinecone(api_key=self.settings.pinecone_api_key)
            index_names = [item["name"] if isinstance(item, dict) else getattr(item, "name", "") for item in pc.list_indexes()]
            if self.settings.pinecone_index_name not in index_names:
                pc.create_index(
                    name=self.settings.pinecone_index_name,
                    dimension=self.vector_dimension,
                    metric="cosine",
                    spec=ServerlessSpec(cloud=self.settings.pinecone_cloud, region=self.settings.pinecone_region),
                    deletion_protection="disabled",
                )
            index = pc.Index(self.settings.pinecone_index_name)
            self._upsert_black_swan_catalog(index)
            response = await asyncio.to_thread(
                index.query,
                vector=vector.tolist(),
                top_k=top_k,
                include_metadata=True,
                include_values=False,
                filter=filter_,
            )
            raw_matches = getattr(response, "matches", []) or response.get("matches", [])
            normalized = []
            for match in raw_matches:
                metadata = getattr(match, "metadata", None) or match.get("metadata", {})
                score = float(getattr(match, "score", None) if getattr(match, "score", None) is not None else match.get("score", 0.0))
                normalized.append({"score": score, "metadata": metadata})
            return normalized
        except Exception:
            return []

    async def _stage_pending_lead_lag_events(self, macro_context: dict) -> None:
        metrics = macro_context["macro_metrics"]
        if float(metrics.get("nasdaq_1h_return", 0.0)) > -0.015:
            return
        pending = self.cache.get_json("macro:pending_lead_lag") or {"events": []}
        bucket_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
        dedupe_id = f"nasdaq-btc-{bucket_id}"
        if any(event["event_id"] == dedupe_id for event in pending["events"]):
            return
        pending["events"].append(
            {
                "event_id": dedupe_id,
                "staged_at": datetime.now(timezone.utc).isoformat(),
                "resolve_after": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
                "lead_asset": "nasdaq",
                "lag_asset": "btc",
                "lead_move_threshold": -0.015,
                "context": metrics,
            }
        )
        self.cache.set_json("macro:pending_lead_lag", pending, ttl=self.settings.monitor_state_ttl_seconds)

    async def _resolve_pending_lead_lag_events(self, macro_context: dict) -> None:
        pending = self.cache.get_json("macro:pending_lead_lag") or {"events": []}
        unresolved = []
        now = datetime.now(timezone.utc)
        btc_30m_return = float(macro_context["macro_metrics"].get("btc_30m_return", 0.0))
        if not pending["events"]:
            return
        for event in pending["events"]:
            resolve_after = datetime.fromisoformat(event["resolve_after"])
            if resolve_after.tzinfo is None:
                resolve_after = resolve_after.replace(tzinfo=timezone.utc)
            if resolve_after > now:
                unresolved.append(event)
                continue
            record = {
                "id": event["event_id"],
                "values": self._embed(json.dumps(event, sort_keys=True)).tolist(),
                "metadata": {
                    "asset_class": "macro",
                    "event_type": "nasdaq_leadlag",
                    "time_relevance": "1h_to_30m",
                    "lead_asset": event["lead_asset"],
                    "lag_asset": event["lag_asset"],
                    "lead_move_pct": float(event["context"].get("nasdaq_1h_return", 0.0)),
                    "lag_move_pct": btc_30m_return,
                    "lag_dump_outcome": 1.0 if btc_30m_return <= -0.01 else 0.0,
                    "observed_at": now.isoformat(),
                },
            }
            await self._upsert_macro_context_record(record)
        self.cache.set_json("macro:pending_lead_lag", {"events": unresolved}, ttl=self.settings.monitor_state_ttl_seconds)

    async def _upsert_macro_context_record(self, record: dict) -> None:
        self._append_local_archive(record)
        if not self.settings.pinecone_api_key or Pinecone is None or ServerlessSpec is None:
            return
        try:
            pc = Pinecone(api_key=self.settings.pinecone_api_key)
            index_names = [item["name"] if isinstance(item, dict) else getattr(item, "name", "") for item in pc.list_indexes()]
            if self.settings.pinecone_index_name not in index_names:
                pc.create_index(
                    name=self.settings.pinecone_index_name,
                    dimension=self.vector_dimension,
                    metric="cosine",
                    spec=ServerlessSpec(cloud=self.settings.pinecone_cloud, region=self.settings.pinecone_region),
                    deletion_protection="disabled",
                )
            index = pc.Index(self.settings.pinecone_index_name)
            await asyncio.to_thread(index.upsert, vectors=[record])
        except Exception:
            return

    def _query_local_lead_lag(self, lead_asset: str, lag_asset: str, lag_window_minutes: int) -> list[dict]:
        matches = []
        if not self.archive_path.exists():
            return matches
        for line in self.archive_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            metadata = record.get("metadata", {})
            if (
                metadata.get("lead_asset") == lead_asset
                and metadata.get("lag_asset") == lag_asset
                and metadata.get("time_relevance") == f"1h_to_{lag_window_minutes}m"
            ):
                matches.append({"score": 1.0, "metadata": metadata})
        return matches[-32:]

    def _upsert_black_swan_catalog(self, index) -> None:
        vectors = []
        for event in self.event_catalog:
            vectors.append(
                {
                    "id": event.event_id,
                    "values": self._event_vector(event).tolist(),
                    "metadata": {
                        "event_id": event.event_id,
                        "name": event.name,
                        "event_date": event.event_date,
                        "asset_class": "macro",
                        "event_type": "black_swan",
                        "time_relevance": "historical",
                        "stress_signature": event.stress_signature,
                    },
                }
            )
        index.upsert(vectors=vectors)

    def _tighten_trailing_stops(self, *, bubble_risk_score: float, reason: str) -> list[StopTighteningAction]:
        actions: list[StopTighteningAction] = []
        tighten_factor = max(0.40, 0.88 - bubble_risk_score * 0.45)
        for trade in self.redis_state_manager.restore_active_trades():
            trade_id = str(trade.get("trade_id", ""))
            if not trade_id:
                continue
            side = str(trade.get("side", "BUY"))
            entry = float(trade.get("entry", 0.0))
            old_trailing = float(trade.get("trailing_stop_pct", 0.004))
            old_stop_loss = float(trade.get("stop_loss", 0.0))
            new_trailing = round(max(0.0012, old_trailing * tighten_factor), 6)
            if side == "BUY":
                candidate_stop = entry * (1 - new_trailing)
                new_stop_loss = round(max(old_stop_loss, candidate_stop), 8)
            else:
                candidate_stop = entry * (1 + new_trailing)
                new_stop_loss = round(min(old_stop_loss or candidate_stop, candidate_stop), 8)
            updated_trade = {
                **trade,
                "trailing_stop_pct": new_trailing,
                "stop_loss": new_stop_loss,
                "risk_overlay": "BUBBLE_RISK",
                "risk_overlay_reason": reason,
            }
            self.redis_state_manager.save_active_trade(trade_id, updated_trade)
            if self.firestore is not None:
                self.firestore.update_trade(
                    trade_id,
                    {
                        "trailing_stop_pct": new_trailing,
                        "stop_loss": new_stop_loss,
                        "risk_overlay": "BUBBLE_RISK",
                        "risk_overlay_reason": reason,
                    },
                )
            actions.append(
                StopTighteningAction(
                    trade_id=trade_id,
                    user_id=str(trade.get("user_id", "system")),
                    symbol=str(trade.get("symbol", "")),
                    side=side,
                    old_trailing_stop_pct=old_trailing,
                    new_trailing_stop_pct=new_trailing,
                    old_stop_loss=old_stop_loss,
                    new_stop_loss=new_stop_loss,
                )
            )
        return actions

    async def _fetch_series(self, alias: str, ticker: str) -> pd.DataFrame:
        cached = self.cache.get_json(f"macro:series:{alias}")
        try:
            frame = await asyncio.to_thread(
                yf.download,
                tickers=ticker,
                period="5d",
                interval="5m",
                progress=False,
                auto_adjust=True,
                threads=False,
            ) if yf is not None else pd.DataFrame()
            if frame is None or frame.empty:
                raise ValueError(f"Empty macro frame for {alias}")
            if isinstance(frame.columns, pd.MultiIndex):
                frame.columns = frame.columns.get_level_values(0)
            frame = frame.reset_index(drop=True)
            if "Close" not in frame:
                raise ValueError(f"Missing close series for {alias}")
            normalized = frame[[column for column in frame.columns if column in {"Close", "Volume"}]].copy()
            if "Volume" not in normalized:
                normalized["Volume"] = 0.0
            self.cache.set_json(
                f"macro:series:{alias}",
                {"rows": normalized.to_dict(orient="records")},
                ttl=self.settings.monitor_state_ttl_seconds,
            )
            return normalized
        except Exception:
            if cached and cached.get("rows"):
                return pd.DataFrame(cached["rows"])
            raise

    def _compute_macro_metrics(self, frames: dict[str, pd.DataFrame]) -> dict:
        dxy_1h = self._window_return(frames.get("dxy"), 12)
        spx_1h = self._window_return(frames.get("spx"), 12)
        nasdaq_1h = self._window_return(frames.get("nasdaq"), 12)
        gold_1h = self._window_return(frames.get("gold"), 12)
        btc_30m = self._window_return(frames.get("btc"), 6)
        us10y_1h_change = self._window_change(frames.get("us10y"), 12)
        safe_haven_rotation = self._bounded(max(dxy_1h, 0.0) * 15 + max(-spx_1h, 0.0) * 12 + max(-nasdaq_1h, 0.0) * 15)
        risk_off_spillover = self._bounded(max(-spx_1h, 0.0) * 12 + max(-nasdaq_1h, 0.0) * 18)
        inflation_hedge_pressure = self._bounded(max(gold_1h, 0.0) * 10 + max(us10y_1h_change / 25, 0.0))
        liquidity_drain_score = self._bounded(max(dxy_1h, 0.0) * 15 + max(us10y_1h_change / 20, 0.0) + max(-nasdaq_1h, 0.0) * 12)
        macro_bearish_score = self._bounded(
            safe_haven_rotation * 0.35
            + risk_off_spillover * 0.35
            + liquidity_drain_score * 0.20
            + max(0.0, -gold_1h) * 0.10
        )
        return {
            "dxy_1h_return": round(dxy_1h, 6),
            "spx_1h_return": round(spx_1h, 6),
            "nasdaq_1h_return": round(nasdaq_1h, 6),
            "gold_1h_return": round(gold_1h, 6),
            "btc_30m_return": round(btc_30m, 6),
            "us10y_1h_change_bps": round(us10y_1h_change * 100, 6),
            "safe_haven_rotation": round(safe_haven_rotation, 6),
            "risk_off_spillover": round(risk_off_spillover, 6),
            "risk_on_spillover": round(self._bounded(max(nasdaq_1h, 0.0) * 12 + max(spx_1h, 0.0) * 10), 6),
            "inflation_hedge_pressure": round(inflation_hedge_pressure, 6),
            "liquidity_drain_score": round(liquidity_drain_score, 6),
            "macro_bearish_score": round(macro_bearish_score, 6),
        }

    def _store_global_bias(self, payload: dict) -> None:
        self.cache.set_json("macro:global_bias", payload, ttl=self.settings.monitor_state_ttl_seconds)

    def _persist_report(self, symbol: str, report: dict) -> None:
        slug = symbol.lower()
        path = self.report_dir / f"{slug}_latest.json"
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        if self.firestore is not None:
            self.firestore.save_performance_snapshot(f"macro-intel:{symbol}", report)

    def _append_local_archive(self, record: dict) -> None:
        with self.archive_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")

    def _event_vector(self, event: HistoricalBlackSwanEvent) -> np.ndarray:
        payload = json.dumps(
            {
                "name": event.name,
                "narrative": event.narrative,
                "keywords": list(event.keywords),
                "stress_signature": event.stress_signature,
            },
            sort_keys=True,
        )
        return self._embed(payload)

    def _embed(self, text: str) -> np.ndarray:
        buckets = np.zeros(self.vector_dimension, dtype=np.float32)
        for token in text.lower().replace(",", " ").replace(":", " ").split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = digest[0] % self.vector_dimension
            sign = 1.0 if digest[1] % 2 == 0 else -1.0
            buckets[idx] += sign * (1.0 + digest[2] / 255.0)
        norm = np.linalg.norm(buckets)
        return buckets if norm == 0 else buckets / norm

    def _cosine_similarity(self, left: np.ndarray, right: np.ndarray) -> float:
        left_norm = np.linalg.norm(left)
        right_norm = np.linalg.norm(right)
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return float(np.dot(left, right) / (left_norm * right_norm))

    def _window_return(self, frame: pd.DataFrame | None, bars: int) -> float:
        if frame is None or frame.empty or "Close" not in frame or len(frame) <= bars:
            return 0.0
        closes = frame["Close"].astype(float).tolist()
        base = closes[-bars - 1]
        latest = closes[-1]
        if abs(base) <= 1e-8:
            return 0.0
        return (latest - base) / base

    def _window_change(self, frame: pd.DataFrame | None, bars: int) -> float:
        if frame is None or frame.empty or "Close" not in frame or len(frame) <= bars:
            return 0.0
        closes = frame["Close"].astype(float).tolist()
        return closes[-1] - closes[-bars - 1]

    def _game_theory_explanation(self, divergence: dict, macro_bias: dict, lead_lag: LeadLagInsight) -> str:
        if macro_bias["regime"] == "BEARISH":
            return (
                "This is a coordination game with asymmetric exits: public hype keeps weaker hands long, "
                "but rising DXY/risk-off pressure rewards the first sellers. When the crowd sees Nasdaq-led stress "
                f"and a {lead_lag.probability:.1%} BTC follow-through probability, holding becomes dominated by de-risking."
            )
        return (
            "Macro pressure is not strong enough to force a crowded exit, so sentiment and on-chain flow remain the main equilibrating signals."
        )

    def _seed_events(self) -> tuple[HistoricalBlackSwanEvent, ...]:
        return (
            HistoricalBlackSwanEvent(
                event_id="ftx-crash",
                name="FTX Crash",
                event_date="2022-11-08",
                narrative="Exchange solvency shock, contagion, trust collapse, rapid exchange inflows, confidence vacuum.",
                keywords=("exchange-run", "custody-risk", "solvency", "contagion", "forced-selling"),
                stress_signature={
                    "social_hype_score": 0.92,
                    "onchain_buy_volume_score": 0.18,
                    "exchange_inflow_risk": 0.96,
                    "liquidity_stress_score": 0.94,
                    "macro_bearish_score": 0.80,
                },
            ),
            HistoricalBlackSwanEvent(
                event_id="luna-collapse",
                name="Luna Collapse",
                event_date="2022-05-09",
                narrative="Reflexive stablecoin unwind, social conviction stayed high while collateral confidence imploded.",
                keywords=("death-spiral", "stablecoin", "reflexivity", "liquidity-gap", "panic"),
                stress_signature={
                    "social_hype_score": 0.88,
                    "onchain_buy_volume_score": 0.22,
                    "exchange_inflow_risk": 0.84,
                    "liquidity_stress_score": 0.90,
                    "macro_bearish_score": 0.73,
                },
            ),
            HistoricalBlackSwanEvent(
                event_id="fed-rate-hikes",
                name="Fed Rate Hike Shock",
                event_date="2022-06-15",
                narrative="Macro tightening repriced duration and speculative beta; hype decoupled from shrinking liquidity.",
                keywords=("rates", "macro", "liquidity", "duration", "risk-off"),
                stress_signature={
                    "social_hype_score": 0.64,
                    "onchain_buy_volume_score": 0.31,
                    "exchange_inflow_risk": 0.59,
                    "liquidity_stress_score": 0.82,
                    "macro_bearish_score": 0.97,
                },
            ),
        )

    def _bounded(self, value: float) -> float:
        return max(0.0, min(1.0, float(value)))

