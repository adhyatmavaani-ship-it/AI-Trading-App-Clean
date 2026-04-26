from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import websockets

from app.core.config import Settings

if TYPE_CHECKING:
    from app.services.firestore_repo import FirestoreRepository
    from app.services.redis_cache import RedisCache


@dataclass
class ShadowLiquiditySentinel:
    settings: Settings
    cache: RedisCache
    firestore: FirestoreRepository | None = None

    def __post_init__(self) -> None:
        self.artifact_dir = Path(self.settings.model_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir = self.artifact_dir / "shadow_liquidity"
        self.report_dir.mkdir(parents=True, exist_ok=True)

    async def analyze_cross_chain_shadow_liquidity(
        self,
        *,
        symbol: str,
        chain_payloads: dict[str, dict[str, list[dict]]],
    ) -> dict:
        alerts = []
        total_shadow_score = 0.0
        chain_summaries = {}
        for chain, payload in chain_payloads.items():
            mempool_signal = self._detect_mempool_whales(chain, payload.get("pending_transactions", []))
            gas_cluster_signal = self._detect_gas_clusters(chain, payload.get("dust_transfers", []), payload.get("token_buys", []))
            venue_flow_signal = self._detect_dex_cex_shift(chain, payload.get("venue_flows", []))
            chain_score = min(
                1.0,
                mempool_signal["score"] * 0.40
                + gas_cluster_signal["score"] * 0.30
                + venue_flow_signal["score"] * 0.30,
            )
            total_shadow_score = max(total_shadow_score, chain_score)
            chain_alerts = [item for item in (mempool_signal["alert"], gas_cluster_signal["alert"], venue_flow_signal["alert"]) if item]
            alerts.extend(chain_alerts)
            chain_summaries[chain] = {
                "shadow_score": round(chain_score, 6),
                "mempool_signal": mempool_signal,
                "gas_cluster_signal": gas_cluster_signal,
                "venue_flow_signal": venue_flow_signal,
            }
        report = {
            "symbol": symbol,
            "as_of": datetime.now(timezone.utc).isoformat(),
            "shadow_liquidity_score": round(total_shadow_score, 6),
            "alerts": alerts,
            "chain_summaries": chain_summaries,
            "entry_signal": total_shadow_score >= 0.70,
            "headline": self._headline(symbol, total_shadow_score, alerts),
        }
        self._persist_report(symbol, report)
        return report

    async def stream_public_mempool(self, chain: str) -> list[dict]:
        if chain == "solana":
            ws_url = self.settings.solana_ws_url or self.settings.solana_rpc_url
            if not ws_url:
                return []
            return await self._stream_solana_logs(ws_url)
        ws_url = {
            "ethereum": self.settings.ethereum_ws_url or self.settings.ethereum_rpc_url,
            "base": self.settings.base_ws_url or self.settings.base_rpc_url,
        }.get(chain, "")
        if not ws_url:
            return []
        return await self._stream_evm_pending(ws_url)

    def _detect_mempool_whales(self, chain: str, pending_transactions: list[dict]) -> dict:
        public_whales = [
            tx for tx in pending_transactions
            if float(tx.get("value_usd", 0.0)) >= 10_000_000 and not bool(tx.get("private_relay", False))
        ]
        score = min(1.0, sum(float(tx.get("value_usd", 0.0)) for tx in public_whales) / 50_000_000)
        alert = None
        if public_whales:
            alert = (
                f"Whale alert! ${sum(float(tx.get('value_usd', 0.0)) for tx in public_whales) / 1_000_000:.1f}M "
                f"of public mempool liquidity spotted on {chain} before execution."
            )
        return {
            "score": round(score, 6),
            "count": len(public_whales),
            "total_value_usd": round(sum(float(tx.get("value_usd", 0.0)) for tx in public_whales), 2),
            "alert": alert,
        }

    def _detect_gas_clusters(self, chain: str, dust_transfers: list[dict], token_buys: list[dict]) -> dict:
        by_cluster: dict[str, dict[str, Any]] = {}
        for transfer in dust_transfers:
            cluster_id = str(transfer.get("cluster_id", "unknown"))
            bucket = by_cluster.setdefault(cluster_id, {"wallets": set(), "token": transfer.get("token", "unknown"), "received": 0.0})
            bucket["wallets"].add(str(transfer.get("wallet", "")))
            bucket["received"] += float(transfer.get("amount_usd", 0.0))
        buy_counts: dict[str, int] = {}
        for buy in token_buys:
            buy_counts[str(buy.get("cluster_id", "unknown"))] = buy_counts.get(str(buy.get("cluster_id", "unknown")), 0) + 1
        suspicious = [
            {
                "cluster_id": cluster_id,
                "wallets": len(bucket["wallets"]),
                "dust_received_usd": bucket["received"],
                "token": bucket["token"],
                "buy_count": buy_counts.get(cluster_id, 0),
            }
            for cluster_id, bucket in by_cluster.items()
            if len(bucket["wallets"]) >= 50 and buy_counts.get(cluster_id, 0) >= max(10, len(bucket["wallets"]) * 0.5)
        ]
        score = min(1.0, len(suspicious) * 0.35 + sum(item["wallets"] for item in suspicious) / 1000)
        alert = None
        if suspicious:
            top = suspicious[0]
            alert = (
                f"Gas cluster anomaly on {chain}: {top['wallets']} wallets received dust then accumulated "
                f"{top['token']} together, suggesting shadow positioning."
            )
        return {
            "score": round(score, 6),
            "clusters": suspicious,
            "alert": alert,
        }

    def _detect_dex_cex_shift(self, chain: str, venue_flows: list[dict]) -> dict:
        dex_to_cex = sum(float(flow.get("amount_usd", 0.0)) for flow in venue_flows if flow.get("direction") == "DEX_TO_CEX")
        cex_to_dex = sum(float(flow.get("amount_usd", 0.0)) for flow in venue_flows if flow.get("direction") == "CEX_TO_DEX")
        ratio = dex_to_cex / max(cex_to_dex, 1e-8)
        score = min(1.0, max(0.0, ratio - 1.0) / 2)
        alert = None
        if dex_to_cex >= 5_000_000 and ratio >= 2.0:
            alert = (
                f"DEX-CEX shift on {chain}: ${dex_to_cex / 1_000_000:.1f}M moved toward centralized venues, "
                "which often precedes aggressive sell pressure."
            )
        return {
            "score": round(score, 6),
            "dex_to_cex_usd": round(dex_to_cex, 2),
            "cex_to_dex_usd": round(cex_to_dex, 2),
            "ratio": round(ratio, 6),
            "alert": alert,
        }

    async def _stream_evm_pending(self, ws_url: str) -> list[dict]:
        subscription = {"jsonrpc": "2.0", "id": 1, "method": "eth_subscribe", "params": ["newPendingTransactions"]}
        try:
            async with websockets.connect(ws_url) as socket:
                await socket.send(json.dumps(subscription))
                raw = await asyncio.wait_for(socket.recv(), timeout=2)
                payload = json.loads(raw)
                return [{"hash": payload.get("params", {}).get("result")}]
        except Exception:
            return []

    async def _stream_solana_logs(self, ws_url: str) -> list[dict]:
        subscription = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "logsSubscribe",
            "params": ["all", {"commitment": "processed"}],
        }
        try:
            async with websockets.connect(ws_url) as socket:
                await socket.send(json.dumps(subscription))
                raw = await asyncio.wait_for(socket.recv(), timeout=2)
                payload = json.loads(raw)
                return [payload]
        except Exception:
            return []

    def _headline(self, symbol: str, score: float, alerts: list[str]) -> str:
        if score >= 0.70 and alerts:
            return f"Whale alert! Shadow liquidity is moving on {symbol}; charts may lag the real flow."
        if score >= 0.45:
            return f"Shadow liquidity on {symbol} is elevated. Watch for hidden size and venue migration."
        return f"No meaningful hidden-liquidity anomaly detected for {symbol}."

    def _persist_report(self, symbol: str, report: dict) -> None:
        path = self.report_dir / f"{symbol.lower()}_shadow.json"
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        self.cache.set_json(f"shadow_liquidity:{symbol.upper()}", report, ttl=self.settings.monitor_state_ttl_seconds)
        if self.firestore is not None:
            self.firestore.save_performance_snapshot(f"shadow-liquidity:{symbol.upper()}", report)

