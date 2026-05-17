from __future__ import annotations

from typing import Any

from app.services.replay_engine import HistoricalReplayEngine
from app.services.time_series_store import TimeSeriesStore


class EventSourcedReplayStore:
    """Append-only replay log for deterministic market and AI reconstruction."""

    def __init__(self, store: TimeSeriesStore, *, namespace_prefix: str = "eventlog") -> None:
        self.store = store
        self.namespace_prefix = namespace_prefix

    def append_event(
        self,
        *,
        symbol: str,
        event_type: str,
        payload: dict[str, Any],
        max_len: int = 50_000,
    ) -> str | None:
        namespace = self._namespace(symbol)
        result = self.store.append(
            namespace=namespace,
            payload={
                "symbol": symbol.upper(),
                "event_type": event_type,
                "payload": payload,
            },
            max_len=max_len,
        )
        return result.stream_id

    def timeline(self, *, symbol: str, count: int = 1000) -> list[dict[str, Any]]:
        return self.store.range(namespace=self._namespace(symbol), count=count)

    def validate(self, *, symbol: str, count: int = 1000) -> dict[str, Any]:
        events = [
            dict(row.get("payload") or row)
            for row in self.timeline(symbol=symbol, count=count)
        ]
        return HistoricalReplayEngine().validate(events).as_dict()

    def _namespace(self, symbol: str) -> str:
        return f"{self.namespace_prefix}:{symbol.upper()}"
