import pandas as pd


class FinvizCleaner:

    @staticmethod
    def clean(df: pd.DataFrame):

        df = df.copy()

        # Remove % sign
        if "Change" in df.columns:
            df["Change"] = (
                df["Change"]
                .astype(str)
                .str.replace("%", "", regex=False)
                .astype(float)
            )

        return df