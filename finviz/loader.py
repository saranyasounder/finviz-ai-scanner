from __future__ import annotations

from pathlib import Path

import pandas as pd
from loguru import logger

from utils.exceptions import EmptyScreenerError


class FinvizLoader:
    """Loads a downloaded Finviz screener CSV into a DataFrame."""

    def __init__(self, csv_file: Path):
        self.csv_file = Path(csv_file)

    def load(self) -> pd.DataFrame:
        logger.info(f"Loading {self.csv_file}")

        df = pd.read_csv(self.csv_file)

        if df.empty:
            raise EmptyScreenerError(f"{self.csv_file} contains no data.")

        logger.success(f"Loaded {len(df)} stocks.")

        return df
