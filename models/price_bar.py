from __future__ import annotations

from datetime import date as date_type

from pydantic import BaseModel


class PriceBar(BaseModel):
    """A single OHLCV bar."""

    date: date_type
    open: float
    high: float
    low: float
    close: float
    volume: int
