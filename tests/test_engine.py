from datetime import datetime
from unittest.mock import MagicMock

from engine import TradingEngine
from models.change_event import ChangeEvent, ChangeType
from models.stock_candidate import StockCandidate


def _stock(ticker="AAA", score=10.0) -> StockCandidate:
    return StockCandidate(
        ticker=ticker,
        company=ticker,
        sector="Technology",
        industry="Software",
        country="USA",
        price=10.0,
        change=0.0,
        volume=1_000_000,
        score=score,
    )


def _make_engine(previous=None, events=None):
    collector = MagicMock()
    collector.collect.return_value = [_stock()]

    scorer = MagicMock()
    scorer.score_all.return_value = [_stock()]

    snapshot_manager = MagicMock()
    snapshot_manager.load_latest.return_value = previous

    change_detector = MagicMock()
    change_detector.detect.return_value = events or []

    enrichment_service = MagicMock()
    enrichment_service.enrich.side_effect = lambda candidates: candidates

    claude_analyzer = MagicMock()
    claude_analyzer.analyze.return_value = []

    conviction_scorer = MagicMock()
    conviction_scorer.must_watch_top_n = 5
    conviction_scorer.rank.side_effect = lambda stocks: stocks
    conviction_scorer.score.return_value = 50.0

    outcome_tracker = MagicMock()

    report_generator = MagicMock()
    report_generator.generate.return_value = "<html></html>"

    email_service = MagicMock()

    engine = TradingEngine(
        collector=collector,
        scorer=scorer,
        snapshot_manager=snapshot_manager,
        change_detector=change_detector,
        enrichment_service=enrichment_service,
        claude_analyzer=claude_analyzer,
        conviction_scorer=conviction_scorer,
        outcome_tracker=outcome_tracker,
        report_generator=report_generator,
        email_service=email_service,
        top_n=10,
    )

    return (
        engine,
        snapshot_manager,
        change_detector,
        enrichment_service,
        claude_analyzer,
        conviction_scorer,
        outcome_tracker,
        email_service,
    )


def test_initial_scan_analyzes_top_n_and_emails_but_skips_change_detection():
    (
        engine,
        snapshot_manager,
        change_detector,
        enrichment_service,
        claude_analyzer,
        conviction_scorer,
        outcome_tracker,
        email_service,
    ) = _make_engine(previous=None)

    engine.run()

    change_detector.detect.assert_not_called()
    enrichment_service.enrich.assert_called_once()
    claude_analyzer.analyze.assert_called_once()
    email_service.send.assert_called_once()
    snapshot_manager.save.assert_called_once()


def test_no_changes_skips_enrichment_claude_and_email():
    (
        engine,
        snapshot_manager,
        change_detector,
        enrichment_service,
        claude_analyzer,
        conviction_scorer,
        outcome_tracker,
        email_service,
    ) = _make_engine(previous=[_stock()], events=[])

    engine.run()

    enrichment_service.enrich.assert_not_called()
    claude_analyzer.analyze.assert_not_called()
    email_service.send.assert_not_called()
    snapshot_manager.save.assert_called_once()


def test_changes_trigger_enrichment_claude_and_email():
    event = ChangeEvent(
        ticker="AAA",
        change_type=ChangeType.SCORE_CHANGE,
        old_value=5,
        new_value=10,
        timestamp=datetime.now(),
        description="AAA score changed.",
    )
    (
        engine,
        snapshot_manager,
        change_detector,
        enrichment_service,
        claude_analyzer,
        conviction_scorer,
        outcome_tracker,
        email_service,
    ) = _make_engine(previous=[_stock()], events=[event])

    claude_analyzer.analyze.return_value = [_stock(ticker="AAA")]

    engine.run()

    enrichment_service.enrich.assert_called_once()
    claude_analyzer.analyze.assert_called_once()
    conviction_scorer.rank.assert_called_once()
    outcome_tracker.log_signal.assert_called_once()
    outcome_tracker.record_due_checkpoints.assert_called_once()
    email_service.send.assert_called_once()
    snapshot_manager.save.assert_called_once()


def test_record_due_checkpoints_runs_every_cycle_even_with_no_changes():
    (
        engine,
        snapshot_manager,
        change_detector,
        enrichment_service,
        claude_analyzer,
        conviction_scorer,
        outcome_tracker,
        email_service,
    ) = _make_engine(previous=[_stock()], events=[])

    engine.run()

    outcome_tracker.log_signal.assert_not_called()
    outcome_tracker.record_due_checkpoints.assert_called_once()


def test_subject_reflects_top_must_watch_ticker():
    event = ChangeEvent(
        ticker="AAA",
        change_type=ChangeType.SCORE_CHANGE,
        old_value=5,
        new_value=10,
        timestamp=datetime.now(),
        description="AAA score changed.",
    )
    (
        engine,
        snapshot_manager,
        change_detector,
        enrichment_service,
        claude_analyzer,
        conviction_scorer,
        outcome_tracker,
        email_service,
    ) = _make_engine(previous=[_stock()], events=[event])
    claude_analyzer.analyze.return_value = [_stock(ticker="AAA")]

    engine.run()

    _, kwargs = email_service.send.call_args
    assert kwargs["subject"] == "Must-Watch: AAA"


def test_enrichment_failure_still_allows_claude_and_email():
    (
        engine,
        snapshot_manager,
        change_detector,
        enrichment_service,
        claude_analyzer,
        conviction_scorer,
        outcome_tracker,
        email_service,
    ) = _make_engine(previous=None)
    enrichment_service.enrich.side_effect = RuntimeError("browser crashed")

    engine.run()

    claude_analyzer.analyze.assert_called_once()
    email_service.send.assert_called_once()
    snapshot_manager.save.assert_called_once()
