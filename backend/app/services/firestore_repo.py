from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
from uuid import uuid4

from google.api_core.exceptions import AlreadyExists
from google.cloud import firestore


class FirestoreRepository:
    def __init__(self, project_id: str):
        self.client = firestore.Client(project=project_id) if project_id else None

    def _collection(self, name: str):
        if self.client is None:
            raise RuntimeError("Firestore project_id is not configured")
        return self.client.collection(name)

    def save_signal(self, payload: dict) -> str:
        signal_id = payload.get("signal_id", str(uuid4()))
        payload["created_at"] = datetime.now(timezone.utc)
        self._collection("signals").document(signal_id).set(payload)
        return signal_id

    def save_trade(self, payload: dict) -> str:
        trade_id = payload.get("trade_id", str(uuid4()))
        payload["created_at"] = datetime.now(timezone.utc)
        self._collection("trades").document(trade_id).set(payload)
        return trade_id

    def update_trade(self, trade_id: str, payload: dict) -> None:
        payload["updated_at"] = datetime.now(timezone.utc)
        self._collection("trades").document(trade_id).set(payload, merge=True)

    def load_trade_by_signal_id(self, signal_id: str) -> dict | None:
        if self.client is None or not signal_id:
            return None
        query = self._collection("trades").where("signal_id", "==", signal_id).limit(1).stream()
        for document in query:
            payload = document.to_dict()
            payload.setdefault("trade_id", document.id)
            return payload
        return None

    def log_event(self, level: str, message: str, context: dict | None = None) -> None:
        self._collection("logs").document(str(uuid4())).set(
            {
                "level": level,
                "message": message,
                "context": context or {},
                "created_at": datetime.now(timezone.utc),
            }
        )

    def save_performance_snapshot(self, user_id: str, payload: dict) -> None:
        payload["updated_at"] = datetime.now(timezone.utc)
        self._collection("performance").document(user_id).set(payload, merge=True)

    def save_training_sample(self, payload: dict) -> str:
        sample_id = payload.get("sample_id", payload.get("trade_id", str(uuid4())))
        payload["created_at"] = datetime.now(timezone.utc)
        self._collection("training_samples").document(sample_id).set(payload)
        return sample_id

    def update_training_sample(self, sample_id: str, payload: dict) -> None:
        payload["updated_at"] = datetime.now(timezone.utc)
        self._collection("training_samples").document(sample_id).set(payload, merge=True)

    def list_training_samples(self, limit: int = 5000) -> list[dict]:
        if self.client is None:
            return []
        query = self._collection("training_samples").limit(limit).stream()
        rows: list[dict] = []
        for document in query:
            payload = document.to_dict()
            payload.setdefault("sample_id", document.id)
            rows.append(payload)
        return rows

    def save_model_report(self, report_type: str, payload: dict) -> str:
        report_id = payload.get("report_id", str(uuid4()))
        payload["report_type"] = report_type
        payload["created_at"] = datetime.now(timezone.utc)
        self._collection("model_reports").document(report_id).set(payload)
        return report_id

    def save_whale_event(self, payload: dict) -> str:
        event_id = payload.get("event_id", str(uuid4()))
        payload["created_at"] = datetime.now(timezone.utc)
        self._collection("whale_events").document(event_id).set(payload)
        return event_id

    def save_liquidity_snapshot(self, payload: dict) -> str:
        snapshot_id = payload.get("snapshot_id", str(uuid4()))
        payload["created_at"] = datetime.now(timezone.utc)
        self._collection("liquidity").document(snapshot_id).set(payload)
        return snapshot_id

    def save_sentiment_snapshot(self, payload: dict) -> str:
        snapshot_id = payload.get("snapshot_id", str(uuid4()))
        payload["created_at"] = datetime.now(timezone.utc)
        self._collection("sentiment").document(snapshot_id).set(payload)
        return snapshot_id

    def save_security_scan(self, payload: dict) -> str:
        scan_id = payload.get("scan_id", str(uuid4()))
        payload["created_at"] = datetime.now(timezone.utc)
        self._collection("security_scans").document(scan_id).set(payload)
        return scan_id

    def save_tax_record(self, payload: dict) -> str:
        tax_id = payload.get("tax_id", str(uuid4()))
        payload["created_at"] = datetime.now(timezone.utc)
        self._collection("tax_records").document(tax_id).set(payload)
        return tax_id

    def save_micro_performance(self, payload: dict) -> str:
        perf_id = payload.get("performance_id", str(uuid4()))
        payload["created_at"] = datetime.now(timezone.utc)
        self._collection("micro_performance").document(perf_id).set(payload)
        return perf_id

    def save_meta_decision(self, trade_id: str, payload: dict) -> None:
        payload["updated_at"] = datetime.now(timezone.utc)
        self._collection("meta_decisions").document(trade_id).set(payload, merge=True)

    def load_meta_decision(self, trade_id: str) -> dict | None:
        snapshot = self._collection("meta_decisions").document(trade_id).get()
        if not snapshot.exists:
            return None
        return snapshot.to_dict()

    def save_meta_analytics(self, payload: dict) -> None:
        payload["updated_at"] = datetime.now(timezone.utc)
        self._collection("meta_analytics").document("global").set(payload, merge=True)

    def save_portfolio_concentration_snapshot(self, user_id: str, payload: dict) -> str:
        snapshot_id = payload.get("snapshot_id", str(uuid4()))
        payload["user_id"] = user_id
        payload["created_at"] = datetime.now(timezone.utc)
        self._collection("portfolio_concentration").document(snapshot_id).set(payload)
        return snapshot_id

    def save_factor_attribution_snapshot(self, user_id: str, payload: dict) -> str:
        snapshot_id = payload.get("snapshot_id", str(uuid4()))
        payload["user_id"] = user_id
        payload["created_at"] = datetime.now(timezone.utc)
        self._collection("factor_attribution").document(snapshot_id).set(payload)
        return snapshot_id

    def save_factor_sleeve_performance(self, user_id: str, payload: dict) -> None:
        payload["user_id"] = user_id
        payload["updated_at"] = datetime.now(timezone.utc)
        self._collection("factor_sleeve_performance").document(user_id).set(payload, merge=True)

    def publish_trade_to_public_log(self, trade: dict) -> str:
        trade_id = str(trade.get("trade_id", "") or "").strip()
        if not trade_id:
            raise ValueError("trade_id is required to publish public trade log")
        symbol = str(trade.get("symbol", "") or "").strip().upper()
        entry = round(float(trade.get("entry", 0.0) or 0.0), 8)
        exit_price = round(float(trade.get("exit", 0.0) or 0.0), 8)
        closed_at = self._coerce_datetime(trade.get("closed_at") or trade.get("updated_at") or datetime.now(timezone.utc))
        payload = {
            "symbol": symbol,
            "entry": entry,
            "exit": exit_price,
            "pnl_pct": round(self._trade_pnl_pct(trade), 4),
            "closed_at": closed_at,
            "hash": self._public_trade_hash(
                symbol=symbol,
                entry=entry,
                exit_price=exit_price,
                closed_at=closed_at,
            ),
        }
        if self.client is None:
            return trade_id
        try:
            self._collection("public_trades").document(trade_id).create(payload)
        except AlreadyExists:
            return trade_id
        return trade_id

    def list_closed_trades(self, limit: int = 20) -> list[dict]:
        if self.client is None:
            return []
        query = (
            self._collection("trades")
            .where("status", "==", "CLOSED")
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        rows: list[dict] = []
        for document in query:
            payload = document.to_dict()
            payload.setdefault("trade_id", document.id)
            rows.append(payload)
        return rows

    def load_public_performance_summary(self, trade_limit: int = 1000) -> dict:
        if self.client is None:
            return {
                "win_rate": 0.0,
                "total_pnl_pct": 0.0,
                "total_trades": 0,
                "last_updated": datetime.now(timezone.utc),
            }
        for doc_id in ("public", "global", "aggregate"):
            snapshot = self._collection("performance").document(doc_id).get()
            if snapshot.exists:
                payload = snapshot.to_dict() or {}
                if any(key in payload for key in ("win_rate", "total_pnl_pct", "total_trades")):
                    return {
                        "win_rate": float(payload.get("win_rate", 0.0) or 0.0),
                        "total_pnl_pct": float(payload.get("total_pnl_pct", payload.get("pnl_pct", 0.0)) or 0.0),
                        "total_trades": int(payload.get("total_trades", payload.get("trades", 0)) or 0),
                        "last_updated": payload.get("updated_at", payload.get("last_updated", datetime.now(timezone.utc))),
                    }

        trades = self.list_closed_trades(limit=trade_limit)
        total_trades = len(trades)
        wins = 0
        total_pnl_pct = 0.0
        last_updated = datetime.now(timezone.utc)
        for trade in trades:
            pnl_pct = self._trade_pnl_pct(trade)
            total_pnl_pct += pnl_pct
            wins += int(pnl_pct >= 0)
            last_updated = max(last_updated, self._coerce_datetime(trade.get("updated_at") or trade.get("created_at")))
        return {
            "win_rate": round((wins / total_trades), 4) if total_trades else 0.0,
            "total_pnl_pct": round(total_pnl_pct, 4),
            "total_trades": total_trades,
            "last_updated": last_updated,
        }

    def load_public_daily_results(self, limit: int = 90) -> list[dict]:
        if self.client is None:
            return []
        query = (
            self._collection("daily_results")
            .order_by("date", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        rows: list[dict] = []
        for document in query:
            payload = document.to_dict() or {}
            if "date" in payload:
                rows.append(
                    {
                        "date": str(payload.get("date", "")),
                        "pnl_pct": round(float(payload.get("pnl_pct", payload.get("profit_pct", 0.0)) or 0.0), 4),
                    }
                )
        if rows:
            return list(reversed(rows))

        buckets: dict[str, float] = defaultdict(float)
        for trade in self.list_closed_trades(limit=max(limit * 20, 200)):
            trade_date = self._coerce_datetime(trade.get("updated_at") or trade.get("created_at")).date().isoformat()
            buckets[trade_date] += self._trade_pnl_pct(trade)
        ordered = sorted(buckets.items())[-limit:]
        return [{"date": date, "pnl_pct": round(value, 4)} for date, value in ordered]

    @staticmethod
    def _coerce_datetime(value) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        if isinstance(value, str) and value:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc)

    @staticmethod
    def _trade_pnl_pct(payload: dict) -> float:
        entry = float(payload.get("entry", 0.0) or 0.0)
        exit_price = float(payload.get("exit", payload.get("close_price", 0.0)) or 0.0)
        side = str(payload.get("side", "")).upper()
        if entry > 0 and exit_price > 0:
            directional = (exit_price - entry) / entry
            if side == "SELL":
                directional *= -1
            return directional * 100
        realized_pnl = float(payload.get("profit", payload.get("realized_pnl", 0.0)) or 0.0)
        executed_notional = float(
            payload.get(
                "executed_notional",
                (float(payload.get("executed_quantity", 0.0) or 0.0) * entry),
            ) or 0.0
        )
        if executed_notional > 0:
            return (realized_pnl / executed_notional) * 100
        return 0.0

    @staticmethod
    def _public_trade_hash(*, symbol: str, entry: float, exit_price: float, closed_at: datetime) -> str:
        normalized_timestamp = FirestoreRepository._coerce_datetime(closed_at).isoformat()
        material = f"{symbol}{entry:.8f}{exit_price:.8f}{normalized_timestamp}"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()
