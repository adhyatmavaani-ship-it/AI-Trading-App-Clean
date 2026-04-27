from __future__ import annotations

import asyncio
import csv
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd

from app.core.config import Settings


@dataclass
class HistoricalDataService:
    settings: Settings

    def __post_init__(self) -> None:
        self.base_dir = Path(self.settings.backtest_data_dir)
        self.chunks_dir = self.base_dir / "chunks"
        self.chunks_dir.mkdir(parents=True, exist_ok=True)

    async def load_range(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_at: datetime,
        end_at: datetime,
        on_chunk=None,
    ) -> pd.DataFrame:
        normalized_symbol = str(symbol or "").upper().strip()
        frames: list[pd.DataFrame] = []
        for chunk_start, chunk_end in self._day_chunks(start_at, end_at):
            frame = await self._load_or_fetch_chunk(
                symbol=normalized_symbol,
                timeframe=timeframe,
                start_at=chunk_start,
                end_at=chunk_end,
            )
            if not frame.empty:
                frames.append(frame)
            if on_chunk is not None:
                await on_chunk(chunk_start, chunk_end, frame)
        if not frames:
            return pd.DataFrame()
        combined = pd.concat(frames, ignore_index=True)
        combined = combined.drop_duplicates(subset=["open_time"]).sort_values("open_time").reset_index(drop=True)
        mask = (combined["open_time"] >= int(start_at.timestamp() * 1000)) & (
            combined["open_time"] <= int(end_at.timestamp() * 1000)
        )
        return combined.loc[mask].reset_index(drop=True)

    async def _load_or_fetch_chunk(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_at: datetime,
        end_at: datetime,
    ) -> pd.DataFrame:
        cache_path = self._chunk_path(symbol=symbol, timeframe=timeframe, start_at=start_at)
        if cache_path.exists():
            return self._read_chunk(cache_path)
        frame = await asyncio.to_thread(
            self._fetch_binance_chunk,
            symbol,
            timeframe,
            start_at,
            end_at,
        )
        self._write_chunk(cache_path, frame)
        return frame

    def _fetch_binance_chunk(
        self,
        symbol: str,
        timeframe: str,
        start_at: datetime,
        end_at: datetime,
    ) -> pd.DataFrame:
        start_ms = int(start_at.timestamp() * 1000)
        end_ms = int(end_at.timestamp() * 1000)
        cursor = start_ms
        rows: list[list[float | int]] = []
        while cursor < end_ms:
            params = {
                "symbol": symbol,
                "interval": timeframe,
                "startTime": cursor,
                "endTime": end_ms,
                "limit": 1000,
            }
            url = f"https://api.binance.com/api/v3/klines?{urlencode(params)}"
            with urlopen(url, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not payload:
                break
            for row in payload:
                open_time, open_price, high, low, close, volume = row[:6]
                close_time = int(row[6]) if len(row) > 6 else int(open_time) + self._interval_ms(timeframe) - 1
                rows.append(
                    [
                        int(open_time),
                        float(open_price),
                        float(high),
                        float(low),
                        float(close),
                        float(volume),
                        int(close_time),
                        float(volume) * float(close),
                        0,
                        float(volume) * 0.5,
                        float(volume) * float(close) * 0.5,
                        0,
                    ]
                )
            last_open_time = int(payload[-1][0])
            next_cursor = last_open_time + self._interval_ms(timeframe)
            if next_cursor <= cursor:
                break
            cursor = next_cursor
            if len(payload) < 1000:
                break
        if not rows:
            return pd.DataFrame()
        frame = pd.DataFrame(
            rows,
            columns=[
                "open_time",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "close_time",
                "quote_volume",
                "trades",
                "taker_base",
                "taker_quote",
                "ignore",
            ],
        )
        return frame.drop_duplicates(subset=["open_time"]).sort_values("open_time").reset_index(drop=True)

    def _read_chunk(self, path: Path) -> pd.DataFrame:
        if not path.exists():
            return pd.DataFrame()
        frame = pd.read_csv(path)
        if frame.empty:
            return frame
        for column in ("open", "high", "low", "close", "volume"):
            frame[column] = frame[column].astype(float)
        return frame

    def _write_chunk(self, path: Path, frame: pd.DataFrame) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if frame.empty:
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(
                    [
                        "open_time",
                        "open",
                        "high",
                        "low",
                        "close",
                        "volume",
                        "close_time",
                        "quote_volume",
                        "trades",
                        "taker_base",
                        "taker_quote",
                        "ignore",
                    ]
                )
            return
        frame.to_csv(path, index=False)

    def _chunk_path(self, *, symbol: str, timeframe: str, start_at: datetime) -> Path:
        day_key = start_at.astimezone(timezone.utc).strftime("%Y%m%d")
        return self.chunks_dir / symbol / timeframe / f"{day_key}.csv"

    def _day_chunks(self, start_at: datetime, end_at: datetime):
        current = start_at.astimezone(timezone.utc)
        end = end_at.astimezone(timezone.utc)
        chunk_hours = max(int(self.settings.backtest_chunk_hours), 1)
        while current < end:
            next_point = min(current + timedelta(hours=chunk_hours), end)
            yield current, next_point
            current = next_point

    def _interval_ms(self, timeframe: str) -> int:
        mapping = {
            "1m": 60_000,
            "5m": 300_000,
            "15m": 900_000,
            "1h": 3_600_000,
        }
        return mapping.get(timeframe, 300_000)

