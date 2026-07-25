from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger

from models.stock_candidate import StockCandidate


class SnapshotManager:
    """Persists every scan to data/snapshots/YYYY-MM-DD/HH-MM.json and provides
    access to the latest/previous snapshot plus retention-based cleanup."""

    def __init__(self, directory: Path, retention_days: int):
        self.directory = directory
        self.retention_days = retention_days
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(
        self, stocks: list[StockCandidate], timestamp: Optional[datetime] = None
    ) -> Path:
        timestamp = timestamp or datetime.now()

        day_dir = self.directory / timestamp.strftime("%Y-%m-%d")
        day_dir.mkdir(parents=True, exist_ok=True)

        file_path = day_dir / f"{timestamp.strftime('%H-%M')}.json"

        payload = {
            "timestamp": timestamp.isoformat(),
            "stocks": [stock.model_dump(mode="json") for stock in stocks],
        }

        file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info(f"Saved snapshot with {len(stocks)} stocks to {file_path}")

        return file_path

    def load_latest(self) -> Optional[list[StockCandidate]]:
        files = self._all_snapshot_files()
        if not files:
            return None
        return self._load(files[-1])

    def load_previous(self) -> Optional[list[StockCandidate]]:
        """The snapshot before the latest one - useful for inspection/backtesting.
        Engines comparing "this scan vs the last completed scan" should call
        load_latest() before calling save() for the current scan."""
        files = self._all_snapshot_files()
        if len(files) < 2:
            return None
        return self._load(files[-2])

    def cleanup_old(self, reference_time: Optional[datetime] = None) -> int:
        reference_time = reference_time or datetime.now()
        cutoff = reference_time.timestamp() - (self.retention_days * 86400)

        removed = 0
        for day_dir in self.directory.iterdir():
            if not day_dir.is_dir():
                continue
            try:
                day = datetime.strptime(day_dir.name, "%Y-%m-%d")
            except ValueError:
                continue

            if day.timestamp() < cutoff:
                for f in day_dir.glob("*.json"):
                    f.unlink()
                    removed += 1
                day_dir.rmdir()

        if removed:
            logger.info(
                f"Removed {removed} snapshot(s) older than {self.retention_days} days."
            )

        return removed

    def _all_snapshot_files(self) -> list[Path]:
        return sorted(self.directory.glob("*/*.json"))

    def _load(self, path: Path) -> list[StockCandidate]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return [StockCandidate(**item) for item in payload["stocks"]]
