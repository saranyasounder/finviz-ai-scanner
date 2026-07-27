from datetime import datetime
from zoneinfo import ZoneInfo

from config.settings import MarketHours
from utils.market_calendar import MarketHoursGuard

_EASTERN = ZoneInfo("America/New_York")
_UTC = ZoneInfo("UTC")


def _market_hours() -> MarketHours:
    return MarketHours(
        timezone="America/New_York",
        start_hour=9,
        start_minute=30,
        end_hour=16,
        end_minute=0,
        days="mon-fri",
    )


def _guard(tmp_path, holidays: list[str] | None = None) -> MarketHoursGuard:
    holidays_path = tmp_path / "market_holidays.yaml"
    holiday_lines = "\n".join(f"  - {d}" for d in (holidays or []))
    holidays_path.write_text(f"holidays:\n{holiday_lines}\n", encoding="utf-8")
    return MarketHoursGuard(_market_hours(), holidays_path)


def test_open_during_regular_hours_on_a_weekday(tmp_path):
    guard = _guard(tmp_path)
    wednesday_10am = datetime(2026, 7, 15, 10, 0, tzinfo=_EASTERN)

    assert guard.is_market_open(wednesday_10am) is True


def test_closed_on_a_weekend(tmp_path):
    guard = _guard(tmp_path)
    saturday_10am = datetime(2026, 7, 18, 10, 0, tzinfo=_EASTERN)

    assert guard.is_market_open(saturday_10am) is False


def test_closed_on_a_configured_holiday(tmp_path):
    guard = _guard(tmp_path, holidays=["2026-12-25"])
    christmas_10am = datetime(2026, 12, 25, 10, 0, tzinfo=_EASTERN)

    assert guard.is_market_open(christmas_10am) is False


def test_closed_before_open(tmp_path):
    guard = _guard(tmp_path)
    before_open = datetime(2026, 7, 15, 9, 0, tzinfo=_EASTERN)

    assert guard.is_market_open(before_open) is False


def test_closed_after_close(tmp_path):
    guard = _guard(tmp_path)
    after_close = datetime(2026, 7, 15, 16, 30, tzinfo=_EASTERN)

    assert guard.is_market_open(after_close) is False


def test_exact_open_and_close_boundaries_are_inclusive(tmp_path):
    guard = _guard(tmp_path)

    assert guard.is_market_open(datetime(2026, 7, 15, 9, 30, tzinfo=_EASTERN)) is True
    assert guard.is_market_open(datetime(2026, 7, 15, 16, 0, tzinfo=_EASTERN)) is True


def test_dst_boundary_handled_correctly_via_zoneinfo(tmp_path):
    guard = _guard(tmp_path)

    # 10:00 AM Eastern in summer (EDT, UTC-4) and winter (EST, UTC-5) are
    # different UTC instants - both must resolve to "market open" once
    # converted to America/New_York.
    summer_utc = datetime(2026, 7, 15, 14, 0, tzinfo=_UTC)  # 10:00 EDT
    winter_utc = datetime(2026, 1, 14, 15, 0, tzinfo=_UTC)  # 10:00 EST

    assert guard.is_market_open(summer_utc) is True
    assert guard.is_market_open(winter_utc) is True
