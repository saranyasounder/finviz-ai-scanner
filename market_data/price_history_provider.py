from __future__ import annotations

import pandas as pd
import yfinance as yf
from loguru import logger

from models.price_bar import PriceBar
from utils.exceptions import PriceHistoryError


class PriceHistoryProvider:
    """Provides OHLCV history independent of Finviz, via yfinance."""

    def get_bars(self, ticker: str, lookback_days: int) -> list[PriceBar]:
        """Single-ticker lookup. For a batch of tickers, prefer get_bars_many()
        - one HTTP round trip instead of one per ticker."""

        logger.debug(f"Fetching {lookback_days}d price history for {ticker}")

        history = yf.Ticker(ticker).history(period=f"{lookback_days}d")

        if history.empty:
            raise PriceHistoryError(f"No price history returned for {ticker}")

        return self._bars_from_dataframe(history)

    def get_current_price(self, ticker: str) -> float:
        """A single lightweight current-price lookup, e.g. for an outcome-tracking
        checkpoint. For many tickers at once, prefer get_current_prices_many()."""

        logger.debug(f"Fetching current price for {ticker}")

        try:
            last_price = yf.Ticker(ticker).fast_info["last_price"]
        except Exception as exc:
            raise PriceHistoryError(
                f"No current price available for {ticker}: {exc}"
            ) from exc

        if last_price is None:
            raise PriceHistoryError(f"No current price available for {ticker}")

        return float(last_price)

    def get_current_prices_many(self, tickers: list[str]) -> dict[str, float]:
        """Batched current-price lookup - one HTTP round trip for the whole list."""

        if not tickers:
            return {}

        logger.debug(
            f"Fetching current price for {len(tickers)} ticker(s) in one batch"
        )

        data = yf.download(
            tickers=tickers,
            period="1d",
            group_by="ticker",
            progress=False,
            threads=True,
        )

        prices: dict[str, float] = {}

        for ticker in tickers:
            try:
                ticker_df = (
                    data[ticker] if isinstance(data.columns, pd.MultiIndex) else data
                )
                if ticker_df.empty:
                    raise PriceHistoryError(f"No current price available for {ticker}")
                prices[ticker] = float(ticker_df["Close"].dropna().iloc[-1])
            except Exception as exc:
                logger.error(f"Current price batch fetch failed for {ticker}: {exc}")

        return prices

    def get_bars_many(
        self, tickers: list[str], lookback_days: int
    ) -> dict[str, list[PriceBar]]:
        """Fetches OHLCV history for many tickers in a single batched call,
        instead of one yfinance request per ticker. A ticker with no data or a
        parse failure is logged and simply absent from the result - it doesn't
        drop the rest of the batch."""

        if not tickers:
            return {}

        logger.debug(
            f"Fetching {lookback_days}d price history for {len(tickers)} "
            "ticker(s) in one batch"
        )

        data = yf.download(
            tickers=tickers,
            period=f"{lookback_days}d",
            group_by="ticker",
            progress=False,
            threads=True,
        )

        results: dict[str, list[PriceBar]] = {}

        for ticker in tickers:
            try:
                ticker_df = (
                    data[ticker] if isinstance(data.columns, pd.MultiIndex) else data
                )
                if ticker_df.empty:
                    raise PriceHistoryError(f"No price history returned for {ticker}")
                results[ticker] = self._bars_from_dataframe(ticker_df)
            except Exception as exc:
                logger.error(f"Price history batch fetch failed for {ticker}: {exc}")

        return results

    @staticmethod
    def _bars_from_dataframe(history: pd.DataFrame) -> list[PriceBar]:
        return [
            PriceBar(
                date=index.date(),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=int(row["Volume"]),
            )
            for index, row in history.dropna().iterrows()
        ]
