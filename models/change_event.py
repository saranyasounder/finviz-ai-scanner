from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class ChangeType(str, Enum):
    NEW = "new"
    SCORE_CHANGE = "score_change"
    RELATIVE_VOLUME_CHANGE = "relative_volume_change"
    GAP_CHANGE = "gap_change"
    PRICE_CHANGE = "price_change"
    ENTERED_TOP_N = "entered_top_n"
    LEFT_TOP_N = "left_top_n"


class ChangeEvent(BaseModel):
    ticker: str
    change_type: ChangeType
    old_value: Optional[float] = None
    new_value: Optional[float] = None
    timestamp: datetime
    description: str
