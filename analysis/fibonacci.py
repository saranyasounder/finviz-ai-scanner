from __future__ import annotations

from models.fibonacci_levels import FibonacciLevels, TrendDirection
from models.price_bar import PriceBar
from utils.exceptions import FibonacciAnalysisError

_RETRACEMENT_RATIOS = (0.236, 0.382, 0.5, 0.618, 0.786)
_TREND_EPSILON = 0.02  # 2% move between oldest and newest close counts as a trend


class FibonacciAnalyzer:
    """Pure calculation: swing high/low, trend, and retracement levels from OHLC bars."""

    def analyze(self, bars: list[PriceBar]) -> FibonacciLevels:
        if len(bars) < 2:
            raise FibonacciAnalysisError(
                f"Need at least 2 price bars to compute Fibonacci levels, got {len(bars)}"
            )

        swing_high = max(bar.high for bar in bars)
        swing_low = min(bar.low for bar in bars)
        current_price = bars[-1].close

        trend = self._determine_trend(bars)
        levels = self._compute_levels(swing_high, swing_low, trend)

        candidate_prices = sorted({swing_low, swing_high, *levels.values()})
        nearest_support = max(
            (p for p in candidate_prices if p <= current_price), default=None
        )
        nearest_resistance = min(
            (p for p in candidate_prices if p >= current_price), default=None
        )

        return FibonacciLevels(
            swing_high=swing_high,
            swing_low=swing_low,
            levels=levels,
            nearest_support=nearest_support,
            nearest_resistance=nearest_resistance,
            trend=trend,
        )

    @staticmethod
    def _determine_trend(bars: list[PriceBar]) -> TrendDirection:
        oldest_close = bars[0].close
        newest_close = bars[-1].close

        if oldest_close <= 0:
            return TrendDirection.SIDEWAYS

        change_pct = (newest_close - oldest_close) / oldest_close

        if change_pct > _TREND_EPSILON:
            return TrendDirection.UPTREND
        if change_pct < -_TREND_EPSILON:
            return TrendDirection.DOWNTREND
        return TrendDirection.SIDEWAYS

    @staticmethod
    def _compute_levels(
        swing_high: float, swing_low: float, trend: TrendDirection
    ) -> dict[str, float]:
        span = swing_high - swing_low
        levels: dict[str, float] = {}

        for ratio in _RETRACEMENT_RATIOS:
            if trend == TrendDirection.DOWNTREND:
                price = swing_low + span * ratio
            else:
                price = swing_high - span * ratio
            levels[str(ratio)] = price

        return levels
