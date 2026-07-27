from __future__ import annotations

from loguru import logger

from analysis.fibonacci import FibonacciAnalyzer
from analysis.news_validator import NewsValidator
from browser.browser import Browser
from finviz.news_fetcher import FinvizNewsFetcher
from market_data.price_history_provider import PriceHistoryProvider
from models.news_item import NewsItem
from models.price_bar import PriceBar
from models.stock_candidate import StockCandidate
from utils.exceptions import FibonacciAnalysisError


class EnrichmentService:
    """Populates news + Fibonacci data on a small set of already-selected candidates
    (changed stocks / initial-scan Top N) - never the full screener, since news
    scraping and price-history lookups are too slow/rate-limit-prone to run on
    every row every minute."""

    def __init__(
        self,
        browser: Browser,
        price_history_provider: PriceHistoryProvider,
        fibonacci_analyzer: FibonacciAnalyzer,
        news_validator: NewsValidator,
        fibonacci_lookback_days: int,
        news_max_headlines: int,
        news_fetch_delay_seconds: float,
    ):
        self.browser = browser
        self.price_history_provider = price_history_provider
        self.fibonacci_analyzer = fibonacci_analyzer
        self.news_validator = news_validator
        self.fibonacci_lookback_days = fibonacci_lookback_days
        self.news_max_headlines = news_max_headlines
        self.news_fetch_delay_seconds = news_fetch_delay_seconds

    def enrich(self, candidates: list[StockCandidate]) -> list[StockCandidate]:
        news_by_ticker = self._fetch_all_news(candidates)
        bars_by_ticker = self._fetch_all_price_history(candidates)

        for stock in candidates:
            stock.news_items = news_by_ticker.get(stock.ticker, [])

            try:
                stock.news_validations = self.news_validator.validate(stock)
            except Exception as exc:
                logger.error(f"News validation failed for {stock.ticker}: {exc}")

            bars = bars_by_ticker.get(stock.ticker)
            if bars is None:
                continue

            try:
                stock.fibonacci = self.fibonacci_analyzer.analyze(bars)
            except FibonacciAnalysisError as exc:
                logger.error(f"Fibonacci analysis failed for {stock.ticker}: {exc}")
            except Exception as exc:
                logger.error(f"Unexpected Fibonacci error for {stock.ticker}: {exc}")

        return candidates

    def _fetch_all_news(
        self, candidates: list[StockCandidate]
    ) -> dict[str, list[NewsItem]]:
        context = self.browser.start()
        try:
            page = context.new_page()
            fetcher = FinvizNewsFetcher(page)
            return fetcher.fetch_many(
                [stock.ticker for stock in candidates],
                self.news_max_headlines,
                self.news_fetch_delay_seconds,
            )
        except Exception as exc:
            logger.error(f"News fetching failed for this batch: {exc}")
            return {}
        finally:
            context.close()
            self.browser.stop()

    def _fetch_all_price_history(
        self, candidates: list[StockCandidate]
    ) -> dict[str, list[PriceBar]]:
        try:
            return self.price_history_provider.get_bars_many(
                [stock.ticker for stock in candidates], self.fibonacci_lookback_days
            )
        except Exception as exc:
            logger.error(f"Price history batch fetch failed: {exc}")
            return {}
