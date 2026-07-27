from datetime import date, timedelta

import pytest

from analysis.fibonacci import FibonacciAnalysisError, FibonacciAnalyzer
from models.fibonacci_levels import TrendDirection
from models.price_bar import PriceBar


def _bar(day_offset: int, open_, high, low, close, volume=1_000_000) -> PriceBar:
    return PriceBar(
        date=date(2026, 1, 1) + timedelta(days=day_offset),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def test_raises_with_fewer_than_two_bars():
    analyzer = FibonacciAnalyzer()

    with pytest.raises(FibonacciAnalysisError):
        analyzer.analyze([_bar(0, 10, 11, 9, 10)])


def test_uptrend_detected_and_levels_anchored_from_high():
    analyzer = FibonacciAnalyzer()
    bars = [
        _bar(0, 100, 102, 95, 100),
        _bar(1, 100, 126, 98, 120),
    ]

    levels = analyzer.analyze(bars)

    assert levels.trend == TrendDirection.UPTREND
    assert levels.swing_high == 126
    assert levels.swing_low == 95
    assert levels.levels["0.5"] == pytest.approx(126 - (126 - 95) * 0.5)


def test_downtrend_detected_and_levels_anchored_from_low():
    analyzer = FibonacciAnalyzer()
    bars = [
        _bar(0, 120, 122, 118, 120),
        _bar(1, 100, 105, 95, 98),
    ]

    levels = analyzer.analyze(bars)

    assert levels.trend == TrendDirection.DOWNTREND
    assert levels.levels["0.5"] == pytest.approx(95 + (122 - 95) * 0.5)


def test_sideways_when_change_within_epsilon():
    analyzer = FibonacciAnalyzer()
    bars = [
        _bar(0, 100, 105, 98, 100),
        _bar(1, 100, 104, 99, 101),
    ]

    levels = analyzer.analyze(bars)

    assert levels.trend == TrendDirection.SIDEWAYS


def test_nearest_support_and_resistance_bracket_current_price():
    analyzer = FibonacciAnalyzer()
    bars = [
        _bar(0, 100, 102, 95, 100),
        _bar(1, 100, 126, 98, 120),
    ]

    levels = analyzer.analyze(bars)

    assert levels.nearest_support is not None
    assert levels.nearest_resistance is not None
    assert levels.nearest_support <= 120 <= levels.nearest_resistance
