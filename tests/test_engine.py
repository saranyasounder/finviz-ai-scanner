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

    claude_analyzer = MagicMock()
    claude_analyzer.analyze.return_value = []

    report_generator = MagicMock()
    report_generator.generate.return_value = "<html></html>"

    email_service = MagicMock()

    engine = TradingEngine(
        collector=collector,
        scorer=scorer,
        snapshot_manager=snapshot_manager,
        change_detector=change_detector,
        claude_analyzer=claude_analyzer,
        report_generator=report_generator,
        email_service=email_service,
        top_n=10,
    )

    return engine, snapshot_manager, change_detector, claude_analyzer, email_service


def test_initial_scan_analyzes_top_n_and_emails_but_skips_change_detection():
    engine, snapshot_manager, change_detector, claude_analyzer, email_service = (
        _make_engine(previous=None)
    )

    engine.run()

    change_detector.detect.assert_not_called()
    claude_analyzer.analyze.assert_called_once()
    email_service.send.assert_called_once()
    snapshot_manager.save.assert_called_once()


def test_no_changes_skips_claude_and_email():
    engine, snapshot_manager, change_detector, claude_analyzer, email_service = (
        _make_engine(previous=[_stock()], events=[])
    )

    engine.run()

    claude_analyzer.analyze.assert_not_called()
    email_service.send.assert_not_called()
    snapshot_manager.save.assert_called_once()


def test_changes_trigger_claude_and_email():
    event = ChangeEvent(
        ticker="AAA",
        change_type=ChangeType.SCORE_CHANGE,
        old_value=5,
        new_value=10,
        timestamp=datetime.now(),
        description="AAA score changed.",
    )
    engine, snapshot_manager, change_detector, claude_analyzer, email_service = (
        _make_engine(previous=[_stock()], events=[event])
    )

    engine.run()

    claude_analyzer.analyze.assert_called_once()
    email_service.send.assert_called_once()
    snapshot_manager.save.assert_called_once()
