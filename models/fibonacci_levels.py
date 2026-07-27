from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class TrendDirection(str, Enum):
    UPTREND = "uptrend"
    DOWNTREND = "downtrend"
    SIDEWAYS = "sideways"


class FibonacciLevels(BaseModel):
    """Retracement levels computed from a swing high/low over a lookback window."""

    swing_high: float
    swing_low: float
    levels: dict[str, float]
    nearest_support: Optional[float] = None
    nearest_resistance: Optional[float] = None
    trend: TrendDirection
