from __future__ import annotations

from pathlib import Path

from loguru import logger
from playwright.sync_api import BrowserContext, sync_playwright


class Browser:
    """Wraps a persistent Playwright Chromium context so Finviz Elite login survives restarts."""

    def __init__(self, profile_dir: Path, headless: bool = False):
        self.profile_dir = profile_dir
        self.headless = headless
        self._playwright = None

    def start(self) -> BrowserContext:
        logger.debug(f"Launching persistent browser context at {self.profile_dir}")
        self._playwright = sync_playwright().start()
        return self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.profile_dir),
            headless=self.headless,
            accept_downloads=True,
        )

    def stop(self) -> None:
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None
