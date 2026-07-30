from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class TradeAction(str, Enum):
    """The one decision this pipeline exists to answer: what to do RIGHT NOW."""

    ENTER_NOW = "ENTER_NOW"
    WAIT_FOR_PULLBACK = "WAIT_FOR_PULLBACK"
    ALREADY_EXTENDED = "ALREADY_EXTENDED"
    AVOID = "AVOID"


class AnchorType(str, Enum):
    FIBONACCI_SUPPORT = "FIBONACCI_SUPPORT"
    ESTIMATED = "ESTIMATED"


class ConfidenceGrade(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class NewsAlignment(str, Enum):
    CORROBORATED = "CORROBORATED"
    CONFLICTING = "CONFLICTING"
    INCONCLUSIVE = "INCONCLUSIVE"
    NONE = "NONE"


class EntryZone(BaseModel):
    low: float
    high: float
    anchor_type: AnchorType
    anchor_price: float


class Target(BaseModel):
    price: float
    risk_reward: str
    basis: str


class Confidence(BaseModel):
    score: int
    grade: ConfidenceGrade


class ClaudeAnalysis(BaseModel):
    """A single real-time intraday trading decision for one candidate,
    re-evaluated every 15-minute cycle - not investment research. Every
    field is mandatory (no Optional/None anywhere): the system prompt
    requires the model to never omit or null a field, and strict Pydantic
    validation here is what actually enforces that - a response missing a
    field raises and is caught/logged upstream like any other analysis
    failure, rather than silently accepting a malformed decision."""

    action: TradeAction
    entry_zone: EntryZone
    stop_loss: float
    target: Target
    risk_per_share: float
    invalidation: str
    time_horizon: str
    confidence: Confidence
    news_alignment: NewsAlignment
    reasoning: str
