from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class OutcomeStatus(str, Enum):
    WIN = "win"
    LOSS = "loss"
    PENDING = "pending"


class Checkpoint(BaseModel):
    """A single scheduled follow-up price check for a logged signal."""

    label: str
    due_at: datetime
    recorded_at: Optional[datetime] = None
    recorded_price: Optional[float] = None


class AlertSignal(BaseModel):
    """A candidate that crossed the 'would have alerted' threshold, logged at
    signal time so its real-world outcome can be checked later - this is the
    evidence for whether the scoring/AI-analysis is actually any good."""

    id: Optional[int] = None
    ticker: str
    signaled_at: datetime
    price_at_signal: float
    ai_confidence: Optional[str] = None
    conviction_score: float
    entry_price: Optional[float] = None
    stop_loss_price: Optional[float] = None
    profit_target_price: Optional[float] = None
    news_verdict: Optional[str] = None
