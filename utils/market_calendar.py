from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import yaml

from config.settings import MarketHours

_WEEKDAY_NAMES = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


class MarketHoursGuard:
    """Answers whether NYSE regular trading hours are open right now - timezone/DST
    correct (via zoneinfo) and holiday-aware (via a config-driven holiday list)."""

    def __init__(self, market_hours: MarketHours, holidays_path: Path):
        self.market_hours = market_hours
        self.timezone = ZoneInfo(market_hours.timezone)
        self.trading_days = self._parse_days(market_hours.days)
        self.holidays = self._load_holidays(holidays_path)

    def is_market_open(self, now: Optional[datetime] = None) -> bool:
        now = (now or datetime.now(self.timezone)).astimezone(self.timezone)

        if now.weekday() not in self.trading_days:
            return False

        if now.date() in self.holidays:
            return False

        open_time = time(self.market_hours.start_hour, self.market_hours.start_minute)
        close_time = time(self.market_hours.end_hour, self.market_hours.end_minute)

        return open_time <= now.time() <= close_time

    @staticmethod
    def _parse_days(days: str) -> set[int]:
        if "-" in days:
            start, end = days.split("-")
            return set(range(_WEEKDAY_NAMES[start], _WEEKDAY_NAMES[end] + 1))
        return {_WEEKDAY_NAMES[d.strip()] for d in days.split(",")}

    @staticmethod
    def _load_holidays(path: Path) -> set[date]:
        with path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        return set(raw.get("holidays") or [])
