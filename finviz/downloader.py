from __future__ import annotations

from datetime import datetime
from pathlib import Path

from loguru import logger
from playwright.sync_api import Page


def download(page: Page, download_root: Path, timeout_ms: int = 15000) -> Path:
    """Downloads the current Finviz screener CSV and returns its saved path."""

    now = datetime.now()

    download_dir = download_root / now.strftime("%Y-%m-%d")
    download_dir.mkdir(parents=True, exist_ok=True)

    filename = f"finviz_{now.strftime('%H-%M-%S')}.csv"
    file_path = download_dir / filename

    logger.info("Downloading screener CSV...")

    with page.expect_download(timeout=timeout_ms) as download_info:
        page.get_by_text("Export").click()

    download = download_info.value
    download.save_as(str(file_path))

    logger.success(f"Saved screener CSV to: {file_path}")

    return file_path
