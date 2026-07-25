from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator

from loguru import logger


@contextmanager
def log_execution_time(label: str) -> Iterator[None]:
    """Logs how long the wrapped block took to run, at INFO level."""

    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        logger.info(f"{label} took {elapsed:.2f}s")
