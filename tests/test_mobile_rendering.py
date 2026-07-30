"""Verifies the shared data-table macro actually renders without horizontal
overflow on a phone-width viewport - a real bug (missing box-sizing:
border-box on a td with width:100% + padding-left:50%) was only caught by
measuring this in a real browser, not by reading the CSS. Uses Playwright,
already a project dependency; no network."""

from datetime import datetime, timedelta

from playwright.sync_api import sync_playwright

from analysis.outcome_tracker import AlertOutcomeTracker
from models.claude_analysis import ClaudeAnalysis, Confidence, EntryZone, Target
from models.stock_candidate import StockCandidate
from reports.outcome_report_generator import OutcomeReportGenerator

_PHONE_WIDTH = 375


class _StubPriceProvider:
    def get_current_prices_many(self, tickers):
        return {t: 56.0 for t in tickers}


def _stock(ticker: str) -> StockCandidate:
    analysis = ClaudeAnalysis(
        action="ENTER_NOW",
        entry_zone=EntryZone(
            low=50.0, high=50.0, anchor_type="FIBONACCI_SUPPORT", anchor_price=50.0
        ),
        stop_loss=48.0,
        target=Target(price=55.0, risk_reward="2.0R", basis="test"),
        risk_per_share=2.0,
        invalidation="test",
        time_horizon="Same-session intraday trade only. Exit before market close.",
        confidence=Confidence(score=85, grade="HIGH"),
        news_alignment="NONE",
        reasoning="r",
    )
    return StockCandidate(
        ticker=ticker,
        company=f"{ticker} Corp",
        sector="Technology",
        industry="Software",
        country="USA",
        price=50.0,
        change=1.0,
        volume=1_000_000,
        analysis=analysis,
    )


def _sample_report_html(tmp_path):
    tracker = AlertOutcomeTracker(
        db_path=tmp_path / "outcomes.db",
        checkpoint_minutes=[30],
        price_provider=_StubPriceProvider(),
        conviction_bucket_high=70,
        conviction_bucket_medium=40,
    )
    signaled_at = datetime(2026, 1, 1, 10, 0)
    tracker.log_signal(_stock("AAA"), conviction_score=85.0, signaled_at=signaled_at)
    tracker.record_due_checkpoints(now=signaled_at + timedelta(hours=1))

    report = tracker.build_report()
    return OutcomeReportGenerator().generate_html(report)


def _assert_no_horizontal_overflow(html_path):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": _PHONE_WIDTH, "height": 800})
            page.goto(html_path.as_uri())

            scroll_width = page.evaluate("document.documentElement.scrollWidth")
            client_width = page.evaluate("document.documentElement.clientWidth")

            assert scroll_width <= client_width, (
                f"Horizontal overflow at {_PHONE_WIDTH}px: "
                f"scrollWidth={scroll_width} > clientWidth={client_width}"
            )

            thead_display = page.evaluate(
                "getComputedStyle(document.querySelector('.data-table thead')).display"
            )
            td_display = page.evaluate(
                "getComputedStyle(document.querySelector('.data-table td')).display"
            )
            assert thead_display == "none"
            assert td_display == "block"
        finally:
            browser.close()


def test_outcome_report_has_no_horizontal_overflow_at_phone_width(tmp_path):
    html = _sample_report_html(tmp_path)
    html_path = tmp_path / "outcome_report.html"
    html_path.write_text(html, encoding="utf-8")

    _assert_no_horizontal_overflow(html_path)
