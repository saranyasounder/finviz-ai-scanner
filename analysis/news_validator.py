from __future__ import annotations

from models.news_validation import NewsValidation, NewsVerdict
from models.stock_candidate import StockCandidate

_BULLISH_KEYWORDS = {
    "beats",
    "beat",
    "surge",
    "surges",
    "soar",
    "soars",
    "upgrade",
    "upgraded",
    "raises",
    "raised",
    "record",
    "breakout",
    "rally",
    "rallies",
    "outperform",
    "strong",
    "jump",
    "jumps",
    "gains",
    "wins",
    "approval",
    "approved",
}

_BEARISH_KEYWORDS = {
    "misses",
    "miss",
    "downgrade",
    "downgraded",
    "cuts",
    "cut",
    "plunge",
    "plunges",
    "lawsuit",
    "recall",
    "warns",
    "warning",
    "delay",
    "delayed",
    "weak",
    "sell-off",
    "selloff",
    "falls",
    "drops",
    "investigation",
    "probe",
}

_CHANGE_EPSILON_PCT = 0.5


class NewsValidator:
    """Cross-checks each headline's keyword sentiment against the stock's actual
    price move, producing one NewsValidation per NewsItem (same order)."""

    def validate(self, stock: StockCandidate) -> list[NewsValidation]:
        return [
            self._validate_one(item.headline, stock.change) for item in stock.news_items
        ]

    def _validate_one(self, headline: str, change_pct: float) -> NewsValidation:
        words = set(headline.lower().replace("-", " ").split())
        is_bullish = bool(words & _BULLISH_KEYWORDS)
        is_bearish = bool(words & _BEARISH_KEYWORDS)

        if is_bullish and is_bearish:
            return NewsValidation(
                headline=headline,
                verdict=NewsVerdict.INCONCLUSIVE,
                note="Headline contains both bullish and bearish language.",
            )

        if abs(change_pct) < _CHANGE_EPSILON_PCT:
            return NewsValidation(
                headline=headline,
                verdict=NewsVerdict.INCONCLUSIVE,
                note=f"Price barely moved ({change_pct:+.2f}%), too early to confirm.",
            )

        if is_bullish and change_pct > 0:
            return NewsValidation(
                headline=headline,
                verdict=NewsVerdict.CORROBORATED,
                note=f"Bullish headline matches price up {change_pct:+.2f}%.",
            )

        if is_bearish and change_pct < 0:
            return NewsValidation(
                headline=headline,
                verdict=NewsVerdict.CORROBORATED,
                note=f"Bearish headline matches price down {change_pct:+.2f}%.",
            )

        if is_bullish and change_pct < 0:
            return NewsValidation(
                headline=headline,
                verdict=NewsVerdict.CONFLICTING,
                note=f"Bullish headline but price is down {change_pct:+.2f}%.",
            )

        if is_bearish and change_pct > 0:
            return NewsValidation(
                headline=headline,
                verdict=NewsVerdict.CONFLICTING,
                note=f"Bearish headline but price is up {change_pct:+.2f}%.",
            )

        return NewsValidation(
            headline=headline,
            verdict=NewsVerdict.INCONCLUSIVE,
            note="No clear sentiment keywords found in headline.",
        )
