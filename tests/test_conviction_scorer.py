from pathlib import Path

from analysis.conviction_scorer import ConvictionScorer
from models.claude_analysis import (
    ClaudeAnalysis,
    Confidence,
    EntryZone,
    Target,
)
from models.news_item import NewsItem
from models.news_validation import NewsValidation, NewsVerdict
from models.stock_candidate import StockCandidate

RANKING_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "ranking.yaml"


def _analysis(confidence_score: float, grade: str = "Medium") -> ClaudeAnalysis:
    return ClaudeAnalysis(
        action="ENTER_NOW",
        entry_zone=EntryZone(
            low=9.5, high=10.5, anchor_type="FIBONACCI_SUPPORT", anchor_price=10.0
        ),
        stop_loss=9.0,
        target=Target(price=12.0, risk_reward="2.0R", basis="test"),
        risk_per_share=1.0,
        invalidation="test",
        time_horizon="Same-session intraday trade only. Exit before market close.",
        confidence=Confidence(score=confidence_score, grade=grade.upper()),
        news_alignment="NONE",
        reasoning="test",
    )


def _stock(
    ticker: str,
    momentum_score: float,
    ai_confidence_score: float | None,
    verdict: NewsVerdict | None,
) -> StockCandidate:
    analysis = None
    if ai_confidence_score is not None:
        analysis = _analysis(ai_confidence_score)

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

    high_momentum_conflicting = _stock("HIGHMOM", 85, 60, NewsVerdict.CONFLICTING)
    low_momentum_corroborated = _stock("LOWMOM", 55, 100, NewsVerdict.CORROBORATED)

    ranked = scorer.rank([high_momentum_conflicting, low_momentum_corroborated])

    assert [s.ticker for s in ranked] == ["LOWMOM", "HIGHMOM"]


def test_conviction_ranking_differs_from_raw_score_ranking():
    scorer = _scorer()

    high_momentum_conflicting = _stock("HIGHMOM", 85, 60, NewsVerdict.CONFLICTING)
    low_momentum_corroborated = _stock("LOWMOM", 55, 100, NewsVerdict.CORROBORATED)
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

    # 50*0.4 (momentum) + 50*0.4 (default_ai_confidence) + 0 (no_news modifier)
    assert score == 40.0


def test_ai_confidence_score_used_directly_without_category_lookup():
    scorer = _scorer()
    # confidence.score is used verbatim now - no High/Medium/Low bucket lookup.
    stock = _stock("PRECISE", momentum_score=50, ai_confidence_score=73, verdict=None)

    score = scorer.score(stock)

    # 50*0.4 (momentum) + 73*0.4 (ai confidence, used directly) + 0 (no_news)
    assert score == 49.2


def test_a_large_enough_momentum_and_confidence_gap_can_still_win_despite_conflict():
    scorer = _scorer()

    # A big enough combined momentum+confidence edge can outweigh a single
    # conflicting headline - this is a real, useful case to know about: the
    # -15/+10 modifiers are meaningful but not absolute veto power.
    strong_but_conflicting = _stock("STRONG", 90, 100, NewsVerdict.CONFLICTING)
    weak_but_corroborated = _stock("WEAK", 60, 60, NewsVerdict.CORROBORATED)

    ranked = scorer.rank([strong_but_conflicting, weak_but_corroborated])

    assert [s.ticker for s in ranked] == ["STRONG", "WEAK"]
