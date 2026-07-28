"""CLI entrypoint for the Finviz AI Trading Intelligence Platform.

    python app.py --once    run a single scan cycle if the market is open, no-op otherwise

run_once() is also imported directly by runner.py, which calls it every 15
minutes - the market-hours/holiday gate lives here so both entry points get
it for free instead of checking it in two places. It also triggers the
end-of-day transient-file cleanup, at most once per day, only after market
close, and only once today's pipeline has actually produced a snapshot.
"""

from __future__ import annotations

import argparse
from datetime import datetime

from loguru import logger

from config.settings import Settings, load_settings
from engine import TradingEngine
from utils.logging_config import configure_logging
from utils.market_calendar import MarketHoursGuard
from utils.retention import TransientFileRetention


def run_once() -> None:
    settings = load_settings()
    configure_logging(settings.logging)

    guard = MarketHoursGuard(
        settings.market_hours, settings.market_holidays_config_path
    )

    if guard.is_market_open():
        engine = TradingEngine.from_settings(settings)
        engine.run()
    else:
        logger.info("MARKET CLOSED - skipping this run (no-op).")

    _maybe_run_end_of_day_cleanup(settings, guard)


def _maybe_run_end_of_day_cleanup(settings: Settings, guard: MarketHoursGuard) -> None:
    """Deletes transient downloads/ artifacts once per day, after market close,
    but never before confirming today's pipeline actually produced a snapshot -
    the marker file and same-day-snapshot check together prevent this from
    running twice in one day or before today's run has really finished."""

    now = datetime.now(guard.timezone)
    if guard.is_market_open(now):
        return

    today = now.date()
    marker_path = settings.base_dir / "data" / ".retention_marker"

    if marker_path.exists() and marker_path.read_text().strip() == today.isoformat():
        return

    today_snapshot_dir = settings.snapshots.directory / today.isoformat()
    if not today_snapshot_dir.exists() or not any(today_snapshot_dir.glob("*.json")):
        logger.debug("End-of-day cleanup skipped - no snapshot for today yet.")
        return

    try:
        retention = TransientFileRetention(
            settings.downloads_dir, settings.retention.downloads_keep_days
        )
        retention.cleanup()
    except Exception as exc:
        logger.error(f"End-of-day retention cleanup failed: {exc}")
        return

    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(today.isoformat(), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Finviz AI Trading Intelligence Platform"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        required=True,
        help="Run a single scan cycle if the market is currently open.",
    )
    parser.parse_args()

    run_once()


if __name__ == "__main__":
    main()
