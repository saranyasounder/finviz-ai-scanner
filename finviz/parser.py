from __future__ import annotations

import pandas as pd

from finviz.mapper import FinvizMapper
from models.stock_candidate import StockCandidate


class FinvizParser:
    """Converts a raw screener DataFrame into StockCandidate objects (unscored)."""

    @staticmethod
    def parse(df: pd.DataFrame) -> list[StockCandidate]:
        return [FinvizMapper.map(row) for _, row in df.iterrows()]
