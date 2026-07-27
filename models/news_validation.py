from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class NewsVerdict(str, Enum):
    CORROBORATED = "corroborated"
    CONFLICTING = "conflicting"
    INCONCLUSIVE = "inconclusive"


class NewsValidation(BaseModel):
    """Whether a single headline's sentiment matches the stock's actual price action."""

    headline: str
    verdict: NewsVerdict
    note: str
