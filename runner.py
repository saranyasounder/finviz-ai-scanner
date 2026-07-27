"""Persistent-process entrypoint: ticks every 15 minutes, always. No business
logic and no market-hours awareness here - app.run_once() owns that decision
(so this file behaves identically to `python app.py --once` run on a timer)."""

from __future__ import annotations

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from app import run_once


def _run_safely() -> None:
    try:
        run_once()
    except Exception as exc:
        logger.error(f"Pipeline run failed: {exc}")


def main() -> None:
    scheduler = BlockingScheduler()
    scheduler.add_job(
        _run_safely,
        trigger=IntervalTrigger(minutes=15),
        id="finviz_pipeline",
        max_instances=1,
        coalesce=True,
    )

    logger.info("Runner starting - pipeline checked every 15 minutes.")
    scheduler.start()


if __name__ == "__main__":
    main()
