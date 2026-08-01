from pathlib import Path

from analysis.conviction_scorer import ConvictionScorer
from models.claude_analysis import ClaudeAnalysis, Confidence, EntryZone, Target
from models.stock_candidate import StockCandidate
from reports.report_generator import ReportGenerator

RANKING_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "ranking.yaml"


def _analysis(
    action: str = "ENTER_NOW",
    confidence_score: int = 80,
    confidence_grade: str = "HIGH",
    news_alignment: str = "NONE",
) -> ClaudeAnalysis:
    return ClaudeAnalysis(
        action=action,
        entry_zone=EntryZone(
            low=9.5, high=10.5, anchor_type="FIBONACCI_SUPPORT", anchor_price=10.0
        ),
        stop_loss=9.0,
        target=Target(price=12.0, risk_reward="2.0R", basis="Nearest resistance"),
        risk_per_share=1.0,
        invalidation="Break below 9.0.",
        time_horizon="Same-session intraday trade only. Exit before market close.",
        confidence=Confidence(score=confidence_score, grade=confidence_grade),
        news_alignment=news_alignment,
        reasoning="Strong momentum near support.",
    )


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


def _generator(must_watch_top_n: int | None = None) -> ReportGenerator:
    scorer = ConvictionScorer(RANKING_CONFIG_PATH)
    if must_watch_top_n is not None:
        scorer.must_watch_top_n = must_watch_top_n
    return ReportGenerator(scorer)


def _must_watch_section(html: str) -> str:
    return html.split("Must-Watch Now")[1].split("Trade Alerts")[0]


def _trade_alerts_section(html: str) -> str:
    return html.split("Trade Alerts")[1].split("Other Candidates")[0]


def test_risk_summary_counts_high_beta_and_short_float():
    generator = _generator()
    stocks = [
        _stock("AAA", score=50, beta=2.0, short_float=15.0),
        _stock("BBB", score=40, beta=0.5, short_float=2.0),
    ]

    html = generator.generate(current=stocks, events=[], analyzed=[], not_analyzed=[])

    assert (
        "1 candidate(s) with beta &gt; 1.5" in html
        or "1 candidate(s) with beta > 1.5" in html
    )
    assert "1 candidate(s) with short float" in html


def test_must_watch_respects_top_n_but_trade_alerts_shows_everyone():
    generator = _generator(must_watch_top_n=1)
    ranked = [
        _stock("FIRST", score=90, analysis=_analysis()),
        _stock("SECOND", score=80, analysis=_analysis()),
    ]

    html = generator.generate(
        current=ranked, events=[], analyzed=ranked, not_analyzed=[]
    )

    must_watch_section = _must_watch_section(html)
    trade_alerts_section = _trade_alerts_section(html)

    assert "FIRST" in must_watch_section
    assert "SECOND" not in must_watch_section
    assert "FIRST" in trade_alerts_section
    assert "SECOND" in trade_alerts_section


def test_report_never_renders_placeholders_or_na():
    generator = _generator()
    stock = _stock("AAA", score=50, analysis=_analysis())

    html = generator.generate(
        current=[stock], events=[], analyzed=[stock], not_analyzed=[]
    )

    assert "placeholder" not in html.lower()
    assert "n/a" not in html.lower()


def test_redundant_sections_are_gone():
    generator = _generator()
    stock = _stock("AAA", score=50, analysis=_analysis())

    html = generator.generate(
        current=[stock], events=[], analyzed=[stock], not_analyzed=[]
    )

    assert "New Candidates" not in html
    assert "Updated Candidates" not in html
    assert "Top Ranked Stocks" not in html
    assert "Score Breakdown" not in html


def test_must_watch_table_shows_action_entry_stop_target_confidence_news():
    generator = _generator()
    stock = _stock(
        "AAA",
        score=90,
        analysis=_analysis(
            action="ENTER_NOW",
            confidence_score=82,
            confidence_grade="HIGH",
            news_alignment="CORROBORATED",
        ),
    )

    html = generator.generate(
        current=[stock], events=[], analyzed=[stock], not_analyzed=[]
    )
    section = _must_watch_section(html)

    assert "ENTER NOW" in section
    assert "9.50 - 10.50" in section
    assert "9.00" in section
    assert "12.00" in section
    assert "82 (HIGH)" in section
    assert "CORROBORATED" in section


def test_must_watch_action_colors_map_correctly():
    generator = _generator()
    stocks = [
        _stock("A", score=90, analysis=_analysis(action="ENTER_NOW")),
        _stock("B", score=80, analysis=_analysis(action="WAIT_FOR_PULLBACK")),
        _stock("C", score=70, analysis=_analysis(action="ALREADY_EXTENDED")),
        _stock("D", score=60, analysis=_analysis(action="AVOID")),
    ]
    generator2 = _generator(must_watch_top_n=4)

    html = generator2.generate(
        current=stocks, events=[], analyzed=stocks, not_analyzed=[]
    )
    section = _must_watch_section(html)

    assert "#22c55e" in section  # ENTER_NOW -> green
    assert "#facc15" in section  # WAIT_FOR_PULLBACK -> amber
    assert "#f87171" in section  # ALREADY_EXTENDED/AVOID -> red


def test_must_watch_shows_no_decision_row_when_analysis_missing():
    generator = _generator()
    stock = _stock("AAA", score=50)  # no analysis

    html = generator.generate(
        current=[stock], events=[], analyzed=[stock], not_analyzed=[]
    )
    section = _must_watch_section(html)

    assert "No AI decision this scan" in section


def test_ticker_column_uses_sticky_positioning():
    generator = _generator()
    stock = _stock("AAA", score=50, analysis=_analysis())

    html = generator.generate(
        current=[stock], events=[], analyzed=[stock], not_analyzed=[]
    )

    assert "position: sticky" in html


def test_trade_alert_card_shows_action_badge_as_largest_element_in_order():
    generator = _generator()
    stock = _stock("AAA", score=90, analysis=_analysis(action="ENTER_NOW"))

    html = generator.generate(
        current=[stock], events=[], analyzed=[stock], not_analyzed=[]
    )
    card = _trade_alerts_section(html)

    ticker_pos = card.index("AAA")
    action_pos = card.index("ENTER NOW")
    confidence_pos = card.index("Confidence:")
    entry_pos = card.index("Entry:")
    stop_pos = card.index("Stop:")
    target_pos = card.index("Target:")
    reasoning_pos = card.index("Strong momentum near support.")

    assert (
        ticker_pos
        < action_pos
        < confidence_pos
        < entry_pos
        < stop_pos
        < target_pos
        < reasoning_pos
    )
    assert "font-size: 20px" in card  # action badge is the largest text on the card


def test_trade_alert_card_shows_unavailable_message_when_no_analysis():
    generator = _generator()
    stock = _stock("AAA", score=50)  # no analysis

    html = generator.generate(
        current=[stock], events=[], analyzed=[stock], not_analyzed=[]
    )
    card = _trade_alerts_section(html)

    assert "Analysis unavailable for this stock." in card


def test_no_grid_or_flexbox_in_must_watch_or_trade_alerts():
    generator = _generator()
    stock = _stock("AAA", score=50, analysis=_analysis())

    html = generator.generate(
        current=[stock], events=[], analyzed=[stock], not_analyzed=[]
    )
    combined = _must_watch_section(html) + _trade_alerts_section(html)

    assert "display: flex" not in combined
    assert "display:flex" not in combined
    assert "display: grid" not in combined
    assert "display:grid" not in combined


def _other_candidates_section(html: str) -> str:
    return html.split("Other Candidates")[1].split("Risk Summary")[0]


def test_not_analyzed_candidates_appear_in_other_candidates_section():
    generator = _generator()
    analyzed_stock = _stock("AAA", score=90, analysis=_analysis())
    skipped_stock = _stock("ZZZ", score=15)

    html = generator.generate(
        current=[analyzed_stock, skipped_stock],
        events=[],
        analyzed=[analyzed_stock],
        not_analyzed=[skipped_stock],
    )
    section = _other_candidates_section(html)

    assert "ZZZ" in section
    assert "15.0" in section
    # The skipped stock's ticker shouldn't also leak into Must-Watch/Trade Alerts.
    assert "ZZZ" not in _must_watch_section(html)
    assert "ZZZ" not in _trade_alerts_section(html)


def test_not_analyzed_section_sorted_by_momentum_score_descending():
    generator = _generator()
    low = _stock("LOW", score=20)
    high = _stock("HIGH", score=60)

    html = generator.generate(
        current=[low, high], events=[], analyzed=[], not_analyzed=[low, high]
    )
    section = _other_candidates_section(html)

    assert section.index("HIGH") < section.index("LOW")


def test_other_candidates_section_shows_fallback_message_when_empty():
    generator = _generator()
    stock = _stock("AAA", score=90, analysis=_analysis())

    html = generator.generate(
        current=[stock], events=[], analyzed=[stock], not_analyzed=[]
    )
    section = _other_candidates_section(html)

    assert "Every scanned candidate was AI-analyzed this cycle." in section


def test_other_candidates_section_has_no_action_or_confidence_columns():
    generator = _generator()
    skipped_stock = _stock("ZZZ", score=15)

    html = generator.generate(
        current=[skipped_stock], events=[], analyzed=[], not_analyzed=[skipped_stock]
    )
    section = _other_candidates_section(html)

    assert "Confidence" not in section
    assert "Action" not in section
