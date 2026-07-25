from __future__ import annotations

from pathlib import Path

from loguru import logger

from browser.browser import Browser
from finviz.downloader import download
from finviz.loader import FinvizLoader
from finviz.parser import FinvizParser
from finviz.screener import FinvizScreener
from models.stock_candidate import StockCandidate


class FinvizCollector:
    """Logs into Finviz Elite, downloads the saved screener, and returns unscored StockCandidates."""

    def __init__(
        self,
        browser: Browser,
        screener_url: str,
        downloads_dir: Path,
        download_timeout_ms: int,
    ):
        self.browser = browser
        self.screener_url = screener_url
        self.downloads_dir = downloads_dir
        self.download_timeout_ms = download_timeout_ms

    def collect(self) -> list[StockCandidate]:
        context = self.browser.start()
        try:
            page = context.new_page()

            screener = FinvizScreener(page, self.screener_url)
            screener.open()

            csv_file = download(page, self.downloads_dir, self.download_timeout_ms)
        finally:
            context.close()
            self.browser.stop()

        df = FinvizLoader(csv_file).load()
        stocks = FinvizParser.parse(df)

        logger.info(f"Collected {len(stocks)} candidates from Finviz Elite screener.")
        return stocks
