"""CLI entrypoint for the Finviz AI Trading Intelligence Platform.

    python app.py --once    run a single scan cycle if the market is open, no-op otherwise

run_once() is also imported directly by runner.py, which calls it every 15
minutes - the market-hours/holiday gate lives here so both entry points get
it for free instead of checking it in two places.
"""

from __future__ import annotations

import argparse

from loguru import logger

from config.settings import load_settings
from engine import TradingEngine
from utils.logging_config import configure_logging
from utils.market_calendar import MarketHoursGuard


def run_once() -> None:
    settings = load_settings()
    configure_logging(settings.logging)

    guard = MarketHoursGuard(settings.market_hours, settings.market_holidays_config_path)

    if not guard.is_market_open():
        logger.info("MARKET CLOSED - skipping this run (no-op).")
        return

    engine = TradingEngine.from_settings(settings)
    engine.run()


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
