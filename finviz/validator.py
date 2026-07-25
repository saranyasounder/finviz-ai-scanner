import pandas as pd


REQUIRED_COLUMNS = [
    "Ticker",
    "Company",
    "Sector",
    "Industry",
    "Country",
    "Market Cap",
    "Price",
    "Change",
    "Volume",
]


class FinvizValidator:

    @staticmethod
    def validate(df: pd.DataFrame):

        missing = [
            c for c in REQUIRED_COLUMNS
            if c not in df.columns
        ]

        if missing:
            raise ValueError(
                f"Missing columns: {missing}"
            )

        return True