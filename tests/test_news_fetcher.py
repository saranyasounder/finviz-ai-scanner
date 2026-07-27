from datetime import datetime

from finviz.news_fetcher import _parse_timestamp


def test_parses_full_date_and_time():
    parsed = _parse_timestamp("Jul-27-26 10:30AM")

    assert parsed == datetime(2026, 7, 27, 10, 30)


def test_parses_time_only_and_fills_in_todays_date():
    today = datetime.now()

    parsed = _parse_timestamp("02:15PM")

    assert parsed is not None
    assert parsed.year == today.year
    assert parsed.month == today.month
    assert parsed.day == today.day
    assert parsed.hour == 14
    assert parsed.minute == 15


def test_unparseable_timestamp_returns_none():
    assert _parse_timestamp("not a timestamp") is None


def test_empty_string_returns_none():
    assert _parse_timestamp("") is None
