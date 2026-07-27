from __future__ import annotations

import yfinance as yf
from loguru import logger

from models.price_bar import PriceBar


class PriceHistoryError(Exception):
    """Raised when OHLC history for a ticker cannot be retrieved."""


class PriceHistoryProvider:
    """Provides OHLCV history independent of Finviz, via yfinance."""

    def get_bars(self, ticker: str, lookback_days: int) -> list[PriceBar]:
        logger.debug(f"Fetching {lookback_days}d price history for {ticker}")

        history = yf.Ticker(ticker).history(period=f"{lookback_days}d")

        if history.empty:
            raise PriceHistoryError(f"No price history returned for {ticker}")

        return [
            PriceBar(
                date=index.date(),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=int(row["Volume"]),
            )
            for index, row in history.iterrows()
        ]
