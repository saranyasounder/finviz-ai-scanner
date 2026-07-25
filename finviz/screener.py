from __future__ import annotations

from loguru import logger
from playwright.sync_api import Page


class FinvizScreener:
    """Navigates to a saved Finviz Elite screener view."""

    def __init__(self, page: Page, screener_url: str):
        self.page = page
        self.screener_url = screener_url

    def open(self) -> None:
        logger.info("Opening Finviz Elite Screener...")
        logger.debug(f"Navigating to: {self.screener_url}")

        self.page.goto(self.screener_url)
        self.page.wait_for_load_state("networkidle")

        logger.success("Finviz Elite Screener loaded successfully.")
