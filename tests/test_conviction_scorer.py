from pathlib import Path

from analysis.conviction_scorer import ConvictionScorer
from models.claude_analysis import ClaudeAnalysis
from models.news_item import NewsItem
from models.news_validation import NewsValidation, NewsVerdict
from models.stock_candidate import StockCandidate

RANKING_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "ranking.yaml"


def _stock(
    ticker: str,
    momentum_score: float,
    confidence: str | None,
    verdict: NewsVerdict | None,
) -> StockCandidate:
    analysis = None
    if confidence is not None:
        analysis = ClaudeAnalysis(
            reasoning="r",
            risk="r",
            entry="e",
            stop_loss="s",
            profit_target="t",
            confidence=confidence,
            trade_quality="B",
        )

    news_items = []
    news_validations = []
    if verdict is not None:
        news_items = [NewsItem(headline="Some headline")]
        news_validations = [
            NewsValidation(headline="Some headline", verdict=verdict, note="note")
        ]

    return StockCandidate(
        ticker=ticker,
        company=f"{ticker} Corp",
        sector="Technology",
        industry="Software",
        country="USA",
        price=10.0,
        change=1.0,
        volume=1_000_000,
        score=momentum_score,
        analysis=analysis,
        news_items=news_items,
        news_validations=news_validations,
    )


def _scorer() -> ConvictionScorer:
    return ConvictionScorer(RANKING_CONFIG_PATH)


def test_high_momentum_but_conflicting_ranks_below_lower_momentum_corroborated():
    scorer = _scorer()

    high_momentum_conflicting = _stock("HIGHMOM", 85, "Medium", NewsVerdict.CONFLICTING)
    low_momentum_corroborated = _stock("LOWMOM", 55, "High", NewsVerdict.CORROBORATED)

    ranked = scorer.rank([high_momentum_conflicting, low_momentum_corroborated])

    assert [s.ticker for s in ranked] == ["LOWMOM", "HIGHMOM"]


def test_conviction_ranking_differs_from_raw_score_ranking():
    scorer = _scorer()

    high_momentum_conflicting = _stock("HIGHMOM", 85, "Medium", NewsVerdict.CONFLICTING)
    low_momentum_corroborated = _stock("LOWMOM", 55, "High", NewsVerdict.CORROBORATED)
    stocks = [high_momentum_conflicting, low_momentum_corroborated]

    score_only_order = [
        s.ticker for s in sorted(stocks, key=lambda s: s.score, reverse=True)
    ]
    conviction_order = [s.ticker for s in scorer.rank(stocks)]

    assert score_only_order == ["HIGHMOM", "LOWMOM"]
    assert conviction_order == ["LOWMOM", "HIGHMOM"]
    assert score_only_order != conviction_order


def test_no_news_and_no_analysis_use_neutral_defaults_without_crashing():
    scorer = _scorer()
    stock = _stock("NONEWS", 50, None, None)

    score = scorer.score(stock)

    # 50*0.4 (momentum) + 50*0.4 (default confidence) + 0 (no_news modifier)
    assert score == 40.0


def test_a_large_enough_momentum_and_confidence_gap_can_still_win_despite_conflict():
    scorer = _scorer()

    # A big enough combined momentum+confidence edge can outweigh a single
    # conflicting headline - this is a real, useful case to know about: the
    # -15/+10 modifiers are meaningful but not absolute veto power.
    strong_but_conflicting = _stock("STRONG", 90, "High", NewsVerdict.CONFLICTING)
    weak_but_corroborated = _stock("WEAK", 60, "Medium", NewsVerdict.CORROBORATED)

    ranked = scorer.rank([strong_but_conflicting, weak_but_corroborated])

    assert [s.ticker for s in ranked] == ["STRONG", "WEAK"]
