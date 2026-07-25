from __future__ import annotations

import sys

from loguru import logger

from config.settings import LoggingSettings


def configure_logging(settings: LoggingSettings) -> None:
    """Configures Loguru with a console sink and a rotating file sink. Call once at startup."""

    settings.directory.mkdir(parents=True, exist_ok=True)

    logger.remove()
    logger.add(sys.stderr, level=settings.level, colorize=True)
    logger.add(
        settings.directory / "app.log",
        level=settings.level,
        rotation=settings.rotation,
        retention=settings.retention,
        enqueue=True,
    )
