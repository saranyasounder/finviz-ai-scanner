from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class NewsItem(BaseModel):
    """A single headline scraped from Finviz's per-ticker news table."""

    headline: str
    url: Optional[str] = None
    source: Optional[str] = None
    published_at: Optional[datetime] = None
    raw_timestamp: Optional[str] = None
