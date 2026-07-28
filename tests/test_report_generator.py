from datetime import datetime

from models.change_event import ChangeEvent, ChangeType
from models.claude_analysis import ClaudeAnalysis
from models.fibonacci_levels import FibonacciLevels, TrendDirection
from models.stock_candidate import StockCandidate
from reports.report_generator import ReportGenerator


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


def test_new_candidate_appears_in_new_section_not_updated():
    generator = ReportGenerator(top_n=10, must_watch_top_n=5)
    stock = _stock("AAA", score=50)

    html = generator.generate(
        current=[stock], events=[_event("AAA", ChangeType.NEW)], analyzed=[]
    )

    assert "AAA" in html
    assert "New Candidates (1)" in html
    assert "Updated Candidates (0)" in html


def test_score_change_appears_in_updated_section():
    generator = ReportGenerator(top_n=10, must_watch_top_n=5)
    stock = _stock("BBB", score=60)

    html = generator.generate(
        current=[stock],
        events=[_event("BBB", ChangeType.SCORE_CHANGE)],
        analyzed=[],
    )

    assert "New Candidates (0)" in html
    assert "Updated Candidates (1)" in html


def test_no_events_yields_empty_new_and_updated_sections():
    generator = ReportGenerator(top_n=10, must_watch_top_n=5)
    stock = _stock("CCC", score=40)

    html = generator.generate(current=[stock], events=[], analyzed=[])

    assert "New Candidates (0)" in html
    assert "Updated Candidates (0)" in html
    assert "No new candidates this scan." in html


def test_top_ranked_respects_top_n_limit():
    generator = ReportGenerator(top_n=1, must_watch_top_n=5)
    stocks = [_stock("HIGH", score=90), _stock("LOW", score=10)]

    html = generator.generate(current=stocks, events=[], analyzed=[])

    assert "HIGH" in html
    # LOW only shouldn't appear in the Top Ranked table (top_n=1 truncates it there);
    # it may still not appear anywhere else since it has no events/analysis.
    assert html.count("LOW") == 0


def test_risk_summary_counts_high_beta_and_short_float():
    generator = ReportGenerator(top_n=10, must_watch_top_n=5)
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
    generator = ReportGenerator(top_n=10, must_watch_top_n=1)
    ranked = [_stock("FIRST", score=90), _stock("SECOND", score=80)]

    html = generator.generate(current=ranked, events=[], analyzed=ranked)

    must_watch_section = html.split("Must-Watch Now")[1].split("New Candidates")[0]
    full_analysis_section = html.split("Full Analysis")[1]

    assert "FIRST" in must_watch_section
    assert "SECOND" not in must_watch_section
    assert "FIRST" in full_analysis_section
    assert "SECOND" in full_analysis_section


def test_must_watch_shows_one_line_reason_from_first_sentence():
    generator = ReportGenerator(top_n=10, must_watch_top_n=5)
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

    must_watch_section = html.split("Must-Watch Now")[1].split("New Candidates")[0]
    assert "Strong breakout above resistance." in must_watch_section
    assert "Volume confirms the move" not in must_watch_section


def test_must_watch_omits_entry_zone_when_no_nearest_support():
    generator = ReportGenerator(top_n=10, must_watch_top_n=5)
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

    must_watch_section = html.split("Must-Watch Now")[1].split("New Candidates")[0]
    assert "Entry zone" not in must_watch_section


def test_report_never_renders_placeholders_or_na():
    generator = ReportGenerator(top_n=10, must_watch_top_n=5)
    stock = _stock("AAA", score=50)

    html = generator.generate(current=[stock], events=[], analyzed=[stock])

    assert "placeholder" not in html.lower()
    assert "n/a" not in html.lower()
