"""CLI entrypoint for the Finviz AI Trading Intelligence Platform.

    python app.py --once        run a single scan cycle immediately
    python app.py --schedule    start the APScheduler market-hours loop
"""

from __future__ import annotations

import argparse

from config.settings import load_settings
from engine import TradingEngine
from scheduler import run_scheduler
from utils.logging_config import configure_logging


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Finviz AI Trading Intelligence Platform"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--once", action="store_true", help="Run a single scan cycle immediately."
    )
    mode.add_argument(
        "--schedule", action="store_true", help="Start the market-hours scheduler."
    )
    args = parser.parse_args()

    settings = load_settings()
    configure_logging(settings.logging)

    engine = TradingEngine.from_settings(settings)

    if args.once:
        engine.run()
    else:
        run_scheduler(engine, settings.market_hours)


if __name__ == "__main__":
    main()
