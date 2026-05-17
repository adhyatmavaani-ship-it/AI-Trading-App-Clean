from __future__ import annotations

from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from threading import Lock
from typing import Any


class RealtimeIntegritySequencer:
    """Adds transport metadata without changing the trading payload contract."""

    def __init__(self, *, recent_limit: int = 1024) -> None:
        self._recent_limit = max(int(recent_limit), 32)
        self._lock = Lock()
        self._sequence_by_stream: dict[str, int] = {}
        self._recent_event_ids: OrderedDict[str, None] = OrderedDict()

    def envelope(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        working = dict(payload or {})
        stream = str(working.get("type") or "event").strip() or "event"
        realtime = dict(working.get("realtime") or {})
        published_at = str(
            working.get("published_at")
            or realtime.get("published_at")
            or datetime.now(timezone.utc).isoformat()
        )
        with self._lock:
            sequence_id = int(
                working.get("sequence_id")
                or realtime.get("sequence_id")
                or self._next_sequence_locked(stream)
            )
            event_id = str(
                working.get("event_id")
                or realtime.get("event_id")
                or self._stable_event_id(working, stream=stream, sequence_id=sequence_id)
            )
            if event_id in self._recent_event_ids:
                return None
            self._remember_locked(event_id)

        snapshot_version = int(
            working.get("snapshot_version")
            or realtime.get("snapshot_version")
            or sequence_id
        )
        state_hash = str(
            working.get("state_hash")
            or realtime.get("state_hash")
            or self.state_hash(working)
        )
        checksum = str(
            working.get("integrity_checksum")
            or realtime.get("integrity_checksum")
            or self.integrity_checksum(
                stream=stream,
                sequence_id=sequence_id,
                snapshot_version=snapshot_version,
                state_hash=state_hash,
            )
        )
        sent_at = datetime.now(timezone.utc).isoformat()
        working["event_id"] = event_id
        working["sequence_id"] = sequence_id
        working["snapshot_version"] = snapshot_version
        working["state_hash"] = state_hash
        working["integrity_checksum"] = checksum
        working["published_at"] = published_at
        working["server_sent_at"] = sent_at
        working["realtime"] = {
            **realtime,
            "event_id": event_id,
            "sequence_id": sequence_id,
            "snapshot_version": snapshot_version,
            "state_hash": state_hash,
            "integrity_checksum": checksum,
            "stream": stream,
            "published_at": published_at,
            "server_sent_at": sent_at,
            "replay_protection": True,
        }
        return working

    def _next_sequence_locked(self, stream: str) -> int:
        next_value = self._sequence_by_stream.get(stream, 0) + 1
        self._sequence_by_stream[stream] = next_value
        return next_value

    def _remember_locked(self, event_id: str) -> None:
        self._recent_event_ids[event_id] = None
        self._recent_event_ids.move_to_end(event_id)
        while len(self._recent_event_ids) > self._recent_limit:
            self._recent_event_ids.popitem(last=False)

    @staticmethod
    def _stable_event_id(payload: dict[str, Any], *, stream: str, sequence_id: int) -> str:
        source = {
            "stream": stream,
            "sequence_id": sequence_id,
            "signal_id": payload.get("signal_id"),
            "signal_version": payload.get("signal_version"),
            "trade_id": payload.get("trade_id"),
            "symbol": payload.get("symbol"),
            "timestamp": payload.get("timestamp") or payload.get("published_at"),
        }
        digest = hashlib.sha1(
            json.dumps(source, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:16]
        return f"{stream}:{sequence_id}:{digest}"

    @staticmethod
    def state_hash(payload: dict[str, Any]) -> str:
        ignored = {
            "event_id",
            "sequence_id",
            "snapshot_version",
            "state_hash",
            "integrity_checksum",
            "published_at",
            "server_sent_at",
            "realtime",
        }
        stable = {key: value for key, value in payload.items() if key not in ignored}
        return hashlib.sha1(
            json.dumps(stable, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:16]

    @staticmethod
    def integrity_checksum(
        *,
        stream: str,
        sequence_id: int,
        snapshot_version: int,
        state_hash: str,
    ) -> str:
        raw = f"{stream}:{sequence_id}:{snapshot_version}:{state_hash}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


class RealtimeReplayBuffer:
    def __init__(self, *, max_events_per_stream: int = 512) -> None:
        self._max_events_per_stream = max(int(max_events_per_stream), 64)
        self._lock = Lock()
        self._events_by_stream: dict[str, OrderedDict[int, dict[str, Any]]] = defaultdict(OrderedDict)

    def append(self, envelope: dict[str, Any]) -> None:
        realtime = dict(envelope.get("realtime") or {})
        stream = str(realtime.get("stream") or envelope.get("type") or "event")
        sequence_id = int(envelope.get("sequence_id") or realtime.get("sequence_id") or 0)
        if sequence_id <= 0:
            return
        with self._lock:
            stream_events = self._events_by_stream[stream]
            stream_events[sequence_id] = dict(envelope)
            stream_events.move_to_end(sequence_id)
            while len(stream_events) > self._max_events_per_stream:
                stream_events.popitem(last=False)

    def replay(self, *, stream: str, from_sequence: int, to_sequence: int, limit: int = 128) -> list[dict[str, Any]]:
        normalized_stream = str(stream or "event").strip() or "event"
        start = max(int(from_sequence), 1)
        end = max(int(to_sequence), start)
        max_items = max(1, min(int(limit), 256))
        with self._lock:
            stream_events = self._events_by_stream.get(normalized_stream)
            if not stream_events:
                return []
            events = [
                dict(payload)
                for sequence, payload in stream_events.items()
                if start <= sequence <= end
            ]
        return events[:max_items]

    def diagnostics(self) -> dict[str, Any]:
        with self._lock:
            return {
                stream: {
                    "count": len(events),
                    "oldest_sequence": next(iter(events.keys())) if events else 0,
                    "latest_sequence": next(reversed(events.keys())) if events else 0,
                }
                for stream, events in self._events_by_stream.items()
            }
