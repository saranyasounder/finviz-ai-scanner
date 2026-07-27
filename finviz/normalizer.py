from __future__ import annotations

from typing import Optional, Union

import pandas as pd

_SUFFIX_MULTIPLIERS = {"B": 1_000_000_000, "M": 1_000_000, "K": 1_000}


class FinvizNormalizer:
    """Converts raw Finviz CSV string values (e.g. "1.5B", "12.3%", "-") into numbers."""

    @staticmethod
    def to_float(value: Union[str, float, int, None]) -> Optional[float]:
        if pd.isna(value):
            return None

        text = str(value).strip()
        if text in ("-", ""):
            return None

        text = text.replace("%", "")

        multiplier = 1
        suffix = text[-1:]
        if suffix in _SUFFIX_MULTIPLIERS:
            multiplier = _SUFFIX_MULTIPLIERS[suffix]
            text = text[:-1]

        return float(text) * multiplier

    @staticmethod
    def to_int(value: Union[str, float, int, None]) -> Optional[int]:
        number = FinvizNormalizer.to_float(value)
        if number is None:
            return None

        return int(number)
