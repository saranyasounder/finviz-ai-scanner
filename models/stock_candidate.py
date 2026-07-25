from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from models.claude_analysis import ClaudeAnalysis


class StockCandidate(BaseModel):
    ticker: str
    company: str
    sector: str
    industry: str
    country: str

    market_cap: Optional[float] = None

    price: float
    change: float

    volume: int
    average_volume: Optional[int] = None
    relative_volume: Optional[float] = None

    atr: Optional[float] = None

    float_percent: Optional[float] = None

    rsi: Optional[float] = None

    gap: Optional[float] = None

    performance_4h: Optional[float] = None

    sma20: Optional[float] = None

    sma50: Optional[float] = None

    beta: Optional[float] = None

    short_float: Optional[float] = None

    institutional_ownership: Optional[float] = None

    score: float = 0.0
    score_breakdown: dict[str, float] = {}

    analysis: Optional[ClaudeAnalysis] = None
