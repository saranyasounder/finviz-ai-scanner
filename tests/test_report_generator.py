from datetime import datetime
from pathlib import Path

from analysis.conviction_scorer import ConvictionScorer
from models.change_event import ChangeEvent, ChangeType
from models.claude_analysis import ClaudeAnalysis
from models.fibonacci_levels import FibonacciLevels, TrendDirection
from models.stock_candidate import StockCandidate
from reports.report_generator import ReportGenerator

RANKING_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "ranking.yaml"


def _stock(
    ticker: str, score: float, beta=None, short_float=None, **overrides
) -> StockCandidate:
    base = dict(
        ticker=ticker,
        company=f"{ticker} Corp",
        sector="Technology",
        industry="Software",
        country="USA",
        price=10.0,
        change=1.0,
        volume=1_000_000,
        score=score,
        beta=beta,
        short_float=short_float,
    )
    base.update(overrides)
    return StockCandidate(**base)


def _event(
    ticker: str, change_type: ChangeType, description: str = "changed"
) -> ChangeEvent:
    return ChangeEvent(
        ticker=ticker,
        change_type=change_type,
        old_value=None,
        new_value=None,
        timestamp=datetime.now(),
        description=description,
    )


def _generator(
    must_watch_top_n: int | None = None,
    bucket_high: float = 70.0,
    bucket_medium: float = 40.0,
) -> ReportGenerator:
    scorer = ConvictionScorer(RANKING_CONFIG_PATH)
    if must_watch_top_n is not None:
        scorer.must_watch_top_n = must_watch_top_n
    return ReportGenerator(scorer, bucket_high, bucket_medium)


def test_risk_summary_counts_high_beta_and_short_float():
    generator = _generator()
    stocks = [
        _stock("AAA", score=50, beta=2.0, short_float=15.0),
        _stock("BBB", score=40, beta=0.5, short_float=2.0),
    ]

    html = generator.generate(current=stocks, events=[], analyzed=[])

    assert (
        "1 candidate(s) with beta &gt; 1.5" in html
        or "1 candidate(s) with beta > 1.5" in html
    )
    assert "1 candidate(s) with short float" in html


def test_must_watch_respects_top_n_but_full_analysis_shows_everyone():
    generator = _generator(must_watch_top_n=1)
    ranked = [_stock("FIRST", score=90), _stock("SECOND", score=80)]

    html = generator.generate(current=ranked, events=[], analyzed=ranked)

    must_watch_section = html.split("Must-Watch Now")[1].split("Full Analysis")[0]
    full_analysis_section = html.split("Full Analysis")[1]

    assert "FIRST" in must_watch_section
    assert "SECOND" not in must_watch_section
    assert "FIRST" in full_analysis_section
    assert "SECOND" in full_analysis_section


def test_must_watch_shows_one_line_reason_from_first_sentence():
    generator = _generator()
    stock = _stock(
        "AAA",
        score=90,
        analysis=ClaudeAnalysis(
            reasoning="Strong breakout above resistance. Volume confirms the move with institutional buying.",
            risk="r",
            entry="e",
            stop_loss="95.00",
            profit_target="120.00",
            confidence="High",
            trade_quality="A",
        ),
    )

    html = generator.generate(current=[stock], events=[], analyzed=[stock])

    must_watch_section = html.split("Must-Watch Now")[1].split("Full Analysis")[0]
    assert "Strong breakout above resistance." in must_watch_section
    assert "Volume confirms the move" not in must_watch_section


def test_must_watch_omits_entry_zone_when_no_nearest_support():
    generator = _generator()
    stock = _stock(
        "AAA",
        score=90,
        fibonacci=FibonacciLevels(
            swing_high=100.0,
            swing_low=90.0,
            levels={"0.5": 95.0},
            nearest_support=None,
            nearest_resistance=100.0,
            trend=TrendDirection.SIDEWAYS,
        ),
    )

    html = generator.generate(current=[stock], events=[], analyzed=[stock])

    must_watch_section = html.split("Must-Watch Now")[1].split("Full Analysis")[0]
    assert "Entry zone" not in must_watch_section


def test_report_never_renders_placeholders_or_na():
    generator = _generator()
    stock = _stock("AAA", score=50)

    html = generator.generate(current=[stock], events=[], analyzed=[stock])

    assert "placeholder" not in html.lower()
    assert "n/a" not in html.lower()


def test_redundant_sections_are_gone():
    generator = _generator()
    stock = _stock("AAA", score=50)

    html = generator.generate(
        current=[stock], events=[_event("AAA", ChangeType.NEW)], analyzed=[stock]
    )

    assert "New Candidates" not in html
    assert "Updated Candidates" not in html
    assert "Top Ranked Stocks" not in html
    assert "Score Breakdown" not in html


def test_full_analysis_shows_conviction_score_and_tier():
    generator = _generator(bucket_high=70.0, bucket_medium=40.0)
    # High momentum, high AI confidence, corroborated news -> well above 70.
    stock = _stock(
        "AAA",
        score=90,
        analysis=ClaudeAnalysis(
            reasoning="r",
            risk="r",
            entry="e",
            stop_loss="s",
            profit_target="t",
            confidence="High",
            trade_quality="A",
        ),
    )

    html = generator.generate(current=[stock], events=[], analyzed=[stock])
    card = html.split("Full Analysis")[1]

    assert 'tier-high"' in card
    assert "Conviction" in card


def test_full_analysis_low_conviction_gets_low_tier():
    generator = _generator(bucket_high=70.0, bucket_medium=40.0)
    # Low momentum, no analysis (default confidence 50), no news -> below 40.
    stock = _stock("AAA", score=10)

    html = generator.generate(current=[stock], events=[], analyzed=[stock])
    card = html.split("Full Analysis")[1]

    assert 'tier-low"' in card


def test_change_reason_appears_as_flag_on_full_analysis_card():
    generator = _generator()
    stock = _stock("AAA", score=50)

    html = generator.generate(
        current=[stock],
        events=[
            _event(
                "AAA",
                ChangeType.SCORE_CHANGE,
                description="AAA score changed by +12.3.",
            )
        ],
        analyzed=[stock],
    )
    card = html.split("Full Analysis")[1]

    assert "AAA score changed by +12.3." in card


def test_full_analysis_omits_support_block_when_nothing_to_show():
    generator = _generator()
    # No analysis, no fibonacci, no news -> the de-emphasized support block
    # (risk/fibonacci/news) should not render an empty div.
    stock = _stock("AAA", score=50)

    html = generator.generate(current=[stock], events=[], analyzed=[stock])
    card = html.split("Full Analysis")[1]

    assert "fa-support" not in card
