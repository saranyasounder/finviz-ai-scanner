from __future__ import annotations

import time
from datetime import datetime

from loguru import logger
from playwright.sync_api import Page

from models.news_item import NewsItem
from utils.exceptions import NewsFetchError

_QUOTE_URL = "https://finviz.com/quote.ashx?t={ticker}"
_NEWS_ROW_SELECTOR = "#news-table tr"


class FinvizNewsFetcher:
    """Scrapes the #news-table on a ticker's Finviz quote page for recent headlines."""

    def __init__(self, page: Page):
        self.page = page

    def fetch_many(
        self,
        tickers: list[str],
        max_headlines: int,
        delay_seconds: float = 0.0,
    ) -> dict[str, list[NewsItem]]:
        """Fetches news for each ticker sequentially on the one injected Page,
        pausing delay_seconds between requests so a batch of tickers doesn't
        hammer finviz.com with back-to-back page loads."""

        results: dict[str, list[NewsItem]] = {}

        for i, ticker in enumerate(tickers):
            if i > 0 and delay_seconds > 0:
                time.sleep(delay_seconds)

            try:
                results[ticker] = self._fetch_one(ticker, max_headlines)
            except NewsFetchError as exc:
                logger.error(f"News fetch failed for {ticker}: {exc}")
            except Exception as exc:
                logger.error(f"Unexpected error fetching news for {ticker}: {exc}")

        return results

    def _fetch_one(self, ticker: str, max_headlines: int) -> list[NewsItem]:
        self.page.goto(_QUOTE_URL.format(ticker=ticker))

        try:
            self.page.wait_for_selector(_NEWS_ROW_SELECTOR, timeout=10000)
        except Exception as exc:
            raise NewsFetchError(
                f"News table did not load for {ticker}: {exc}"
            ) from exc

        rows = self.page.query_selector_all(_NEWS_ROW_SELECTOR)
        items: list[NewsItem] = []
        last_date_text = ""

        for row in rows:
            if len(items) >= max_headlines:
                break

            item = self._parse_row(row, last_date_text)
            if item is None:
                continue

            if item.raw_timestamp:
                last_date_text = item.raw_timestamp

            items.append(item)

        return items

    @staticmethod
    def _parse_row(row, last_date_text: str) -> NewsItem | None:
        cells = row.query_selector_all("td")
        if len(cells) < 2:
            return None

        raw_timestamp = cells[0].inner_text().strip() or last_date_text

        link = cells[1].query_selector("a")
        if link is None:
            return None

        headline = link.inner_text().strip()
        url = link.get_attribute("href")

        source_el = cells[1].query_selector("span")
        source = source_el.inner_text().strip("() ") if source_el else None

        return NewsItem(
            headline=headline,
            url=url,
            source=source,
            published_at=_parse_timestamp(raw_timestamp),
            raw_timestamp=raw_timestamp,
        )


def _parse_timestamp(raw: str) -> datetime | None:
    for fmt in ("%b-%d-%y %I:%M%p", "%I:%M%p"):
        try:
            parsed = datetime.strptime(raw, fmt)
            if fmt == "%I:%M%p":
                today = datetime.now()
                parsed = parsed.replace(
                    year=today.year, month=today.month, day=today.day
                )
            return parsed
        except ValueError:
            continue
    return None
