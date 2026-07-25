from __future__ import annotations

from pydantic import BaseModel


class ClaudeAnalysis(BaseModel):
    """Claude's trade write-up for a single changed/top-ranked stock."""

    reasoning: str
    risk: str
    entry: str
    stop_loss: str
    profit_target: str
    confidence: str
    trade_quality: str
