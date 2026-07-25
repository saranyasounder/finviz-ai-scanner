from pathlib import Path

from analysis.momentum_scorer import MomentumScorer
from models.stock_candidate import StockCandidate

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "scoring.yaml"


def _make_stock(**overrides) -> StockCandidate:
    base = dict(
        ticker="TEST",
        company="Test Co",
        sector="Technology",
        industry="Software",
        country="USA",
        price=10.0,
        change=1.0,
        volume=1_000_000,
        relative_volume=6.0,
        gap=6.0,
        atr=2.0,
        rsi=70.0,
        sma20=1.0,
        sma50=1.0,
        beta=2.0,
        short_float=15.0,
        institutional_ownership=60.0,
    )
    base.update(overrides)
    return StockCandidate(**base)


def test_high_thresholds_score_maximally():
    scorer = MomentumScorer(CONFIG_PATH)
    stock = scorer.score(_make_stock())

    assert stock.score_breakdown["relative_volume"] == 25
    assert stock.score_breakdown["gap"] == 20
    assert stock.score == sum(stock.score_breakdown.values())


def test_medium_thresholds_score_less():
    scorer = MomentumScorer(CONFIG_PATH)
    stock = scorer.score(_make_stock(relative_volume=4.0, gap=3.0))

    assert stock.score_breakdown["relative_volume"] == 15
    assert stock.score_breakdown["gap"] == 10


def test_low_values_score_nothing_for_that_rule():
    scorer = MomentumScorer(CONFIG_PATH)
    stock = scorer.score(_make_stock(relative_volume=1.0, gap=0.5))

    assert "relative_volume" not in stock.score_breakdown
    assert "gap" not in stock.score_breakdown


def test_score_all_sorts_descending():
    scorer = MomentumScorer(CONFIG_PATH)
    low = _make_stock(
        ticker="LOW",
        relative_volume=1.0,
        gap=0.5,
        atr=0.1,
        rsi=10,
        sma20=0,
        sma50=0,
        beta=0.1,
        short_float=1,
        institutional_ownership=1,
    )
    high = _make_stock(ticker="HIGH")

    scored = scorer.score_all([low, high])

    assert [s.ticker for s in scored] == ["HIGH", "LOW"]
