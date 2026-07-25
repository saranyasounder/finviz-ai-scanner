import pandas as pd


class FinvizNormalizer:

    @staticmethod
    def to_float(value):

        if pd.isna(value):
            return None

        value = str(value).strip()

        if value in ("-", ""):
            return None

        value = value.replace("%", "")

        multiplier = 1

        if value.endswith("B"):
            multiplier = 1_000_000_000
            value = value[:-1]

        elif value.endswith("M"):
            multiplier = 1_000_000
            value = value[:-1]

        elif value.endswith("K"):
            multiplier = 1_000
            value = value[:-1]

        return float(value) * multiplier

    @staticmethod
    def to_int(value):

        number = FinvizNormalizer.to_float(value)

        if number is None:
            return None

        return int(number)