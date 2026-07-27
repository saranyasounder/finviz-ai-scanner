from __future__ import annotations

import pandas as pd

from finviz.normalizer import FinvizNormalizer
from models.stock_candidate import StockCandidate


class FinvizMapper:
    """Maps a single raw Finviz screener CSV row to a StockCandidate."""

    @staticmethod
    def map(row: pd.Series) -> StockCandidate:
        n = FinvizNormalizer

        return StockCandidate(
            ticker=row["Ticker"],
            company=row["Company"],
            sector=row["Sector"],
            industry=row["Industry"],
            country=row["Country"],
            market_cap=n.to_float(row["Market Cap"]),
            price=n.to_float(row["Price"]),
            change=n.to_float(row["Change"]),
            volume=n.to_int(row["Volume"]),
            average_volume=n.to_int(row["Average Volume"]),
            relative_volume=n.to_float(row["Relative Volume"]),
            atr=n.to_float(row["Average True Range"]),
            float_percent=n.to_float(row["Float %"]),
            rsi=n.to_float(row["Relative Strength Index (14)"]),
            gap=n.to_float(row["Gap"]),
            performance_4h=n.to_float(row["Performance (4 Hours)"]),
            sma20=n.to_float(row["20-Day Simple Moving Average"]),
            sma50=n.to_float(row["50-Day Simple Moving Average"]),
            beta=n.to_float(row["Beta"]),
            short_float=n.to_float(row["Short Float"]),
            institutional_ownership=n.to_float(row["Institutional Ownership"]),
        )
