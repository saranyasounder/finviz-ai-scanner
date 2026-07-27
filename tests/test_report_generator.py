from datetime import datetime

from models.change_event import ChangeEvent, ChangeType
from models.stock_candidate import StockCandidate
from reports.report_generator import ReportGenerator


def _stock(ticker: str, score: float, beta=None, short_float=None) -> StockCandidate:
    return StockCandidate(
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
    generator = ReportGenerator(top_n=10)
    stock = _stock("AAA", score=50)

    html = generator.generate(
        current=[stock], events=[_event("AAA", ChangeType.NEW)], analyzed=[]
    )

    assert "AAA" in html
    assert "New Candidates (1)" in html
    assert "Updated Candidates (0)" in html


def test_score_change_appears_in_updated_section():
    generator = ReportGenerator(top_n=10)
    stock = _stock("BBB", score=60)

    html = generator.generate(
        current=[stock],
        events=[_event("BBB", ChangeType.SCORE_CHANGE)],
        analyzed=[],
    )

    assert "New Candidates (0)" in html
    assert "Updated Candidates (1)" in html


def test_no_events_yields_empty_new_and_updated_sections():
    generator = ReportGenerator(top_n=10)
    stock = _stock("CCC", score=40)

    html = generator.generate(current=[stock], events=[], analyzed=[])

    assert "New Candidates (0)" in html
    assert "Updated Candidates (0)" in html
    assert "No new candidates this scan." in html


def test_top_ranked_respects_top_n_limit():
    generator = ReportGenerator(top_n=1)
    stocks = [_stock("HIGH", score=90), _stock("LOW", score=10)]

    html = generator.generate(current=stocks, events=[], analyzed=[])

    assert "HIGH" in html
    # LOW only shouldn't appear in the Top Ranked table (top_n=1 truncates it there);
    # it may still not appear anywhere else since it has no events/analysis.
    assert html.count("LOW") == 0


def test_risk_summary_counts_high_beta_and_short_float():
    generator = ReportGenerator(top_n=10)
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
