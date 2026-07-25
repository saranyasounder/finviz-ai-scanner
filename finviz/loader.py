from pathlib import Path
import pandas as pd


class FinvizLoader:

    def __init__(self, csv_path: Path):
        self.csv_path = Path(csv_path)

    def load(self) -> pd.DataFrame:

        df = pd.read_csv(self.csv_path)

        print(df.columns.tolist())

        print(f"Loaded {len(df)} stocks")



        return df