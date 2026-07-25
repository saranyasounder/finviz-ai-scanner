from pathlib import Path

import pandas as pd

from loguru import logger


class FinvizLoader:

    def __init__(self, csv_file: Path):

        self.csv_file = Path(csv_file)

    def load(self):

        logger.info(f"Loading {self.csv_file}")

        df = pd.read_csv(self.csv_file)

        if df.empty:
            raise ValueError("CSV contains no data.")

        logger.success(f"Loaded {len(df)} stocks.")

        return df