"""Deletes transient per-run artifacts only - raw screener CSVs under downloads/.

Never touches data/snapshots/, the permanent historical scan store managed by
storage/snapshot_manager.py, which has its own independent retention policy.

Usable as a library (TransientFileRetention) or directly from the command line:

    python -m utils.retention --dry-run
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from loguru import logger


class TransientFileRetention:
    """Deletes downloads/YYYY-MM-DD/ folders older than keep_days. Intended to run
    once at end-of-day, only after today's final scan+email has completed
    successfully - the caller is responsible for that timing; this class only
    knows how to delete, not when it's safe to."""

    def __init__(self, downloads_dir: Path, keep_days: int):
        self.downloads_dir = downloads_dir
        self.keep_days = keep_days

    def cleanup(
        self, dry_run: bool = False, reference_date: Optional[date] = None
    ) -> int:
        reference_date = reference_date or datetime.now().date()
        cutoff = reference_date - timedelta(days=self.keep_days)

        if not self.downloads_dir.exists():
            logger.info(
                f"Retention: {self.downloads_dir} doesn't exist, nothing to do."
            )
            return 0

        removed_files = 0
        freed_bytes = 0

        for day_dir in sorted(self.downloads_dir.iterdir()):
            if not day_dir.is_dir():
                continue

            try:
                folder_date = datetime.strptime(day_dir.name, "%Y-%m-%d").date()
            except ValueError:
                continue

            if folder_date >= cutoff:
                continue

            files = [f for f in day_dir.iterdir() if f.is_file()]
            dir_size = sum(f.stat().st_size for f in files)

            if dry_run:
                logger.info(
                    f"[DRY RUN] Would delete {day_dir} "
                    f"({len(files)} file(s), {dir_size / 1024:.1f} KB)"
                )
            else:
                for f in files:
                    f.unlink()
                day_dir.rmdir()
                logger.info(
                    f"Deleted {day_dir} ({len(files)} file(s), "
                    f"{dir_size / 1024:.1f} KB freed)"
                )

            removed_files += len(files)
            freed_bytes += dir_size

        if removed_files:
            verb = "Would free" if dry_run else "Freed"
            logger.info(
                f"Transient file retention: {verb} {freed_bytes / 1024:.1f} KB "
                f"across {removed_files} file(s) under {self.downloads_dir}."
            )
        else:
            logger.info("Transient file retention: nothing to delete.")

        return removed_files


def _main() -> None:
    from config.settings import load_settings
    from utils.logging_config import configure_logging

    parser = argparse.ArgumentParser(
        description="Clean up transient downloads/ artifacts."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log what would be deleted without deleting anything.",
    )
    args = parser.parse_args()

    settings = load_settings()
    configure_logging(settings.logging)

    retention = TransientFileRetention(
        settings.downloads_dir, settings.retention.downloads_keep_days
    )
    retention.cleanup(dry_run=args.dry_run)


if __name__ == "__main__":
    _main()
