from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from models.alert_signal import OutcomeStatus


class OutcomeEntry(BaseModel):
    """One signal's result as of its latest recorded checkpoint (or PENDING
    if no checkpoint has come due and been recorded yet)."""

    ticker: str
    signaled_at: datetime
    conviction_score: float
    status: OutcomeStatus
    move_pct: Optional[float] = None
    latest_checkpoint_label: Optional[str] = None


class ConvictionBucketStat(BaseModel):
    """Win rate within one conviction-score band - the evidence for whether
    conviction score actually correlates with outcome."""

    bucket: str
    total: int
    wins: int
    losses: int
    pending: int

    @property
    def hit_rate_pct(self) -> Optional[float]:
        decided = self.wins + self.losses
        if decided == 0:
            return None
        return self.wins / decided * 100


class OutcomeReport(BaseModel):
    entries: list[OutcomeEntry]
    total_signals: int
    wins: int
    losses: int
    pending: int
    average_move_pct: Optional[float] = None
    buckets: list[ConvictionBucketStat]

    @property
    def hit_rate_pct(self) -> Optional[float]:
        decided = self.wins + self.losses
        if decided == 0:
            return None
        return self.wins / decided * 100
