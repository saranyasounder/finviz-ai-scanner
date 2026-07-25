"""APScheduler wiring only - no business logic. TradingEngine owns every decision
about what happens during a run; this module only decides *when* run() fires."""

from __future__ import annotations

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from config.settings import MarketHours
from engine import TradingEngine


def build_scheduler(engine: TradingEngine, market_hours: MarketHours) -> BlockingScheduler:
    scheduler = BlockingScheduler(timezone=market_hours.timezone)

    # Covers every minute from start_hour:00 up to (end_hour-1):59.
    scheduler.add_job(
        engine.run,
        trigger=CronTrigger(
            day_of_week=market_hours.days,
            hour=f"{market_hours.start_hour}-{market_hours.end_hour - 1}",
            minute="*",
            timezone=market_hours.timezone,
        ),
        id="trading_engine_minutely",
        max_instances=1,
        coalesce=True,
    )

    # The market-close boundary itself (e.g. exactly 13:00) isn't covered by the
    # range above, which stops at end_hour-1:59 - a second trigger fires once
    # more at exactly end_hour:00 and then the trading day is done.
    scheduler.add_job(
        engine.run,
        trigger=CronTrigger(
            day_of_week=market_hours.days,
            hour=market_hours.end_hour,
            minute=0,
            timezone=market_hours.timezone,
        ),
        id="trading_engine_market_close",
        max_instances=1,
        coalesce=True,
    )

    return scheduler


def run_scheduler(engine: TradingEngine, market_hours: MarketHours) -> None:
    scheduler = build_scheduler(engine, market_hours)

    logger.info(
        f"Scheduler starting: {market_hours.days} "
        f"{market_hours.start_hour:02d}:00-{market_hours.end_hour:02d}:00 "
        f"{market_hours.timezone}"
    )

    scheduler.start()
