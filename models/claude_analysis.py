from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class ClaudeAnalysis(BaseModel):
    """Claude's trade write-up for a single changed/top-ranked stock.

    entry/stop_loss/profit_target stay free text for human-readable emails
    (Claude may qualify them, e.g. "190 near support"); the *_price fields are
    the numeric counterparts needed for quantitative outcome tracking. Claude
    is asked for both; the numeric ones are optional since a model response
    can omit or malform them."""

    reasoning: str
    risk: str
    entry: str
    stop_loss: str
    profit_target: str
    confidence: str
    trade_quality: str

    entry_price: Optional[float] = None
    stop_loss_price: Optional[float] = None
    profit_target_price: Optional[float] = None
