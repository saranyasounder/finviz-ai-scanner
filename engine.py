from __future__ import annotations

from loguru import logger

from analysis.change_detector import ChangeDetector
from analysis.claude_analyzer import ClaudeAnalyzer
from analysis.momentum_scorer import MomentumScorer
from finviz.collector import FinvizCollector
from models.change_event import ChangeType
from notifications.email_service import EmailService
from reports.report_generator import ReportGenerator
from storage.snapshot_manager import SnapshotManager
from utils.timing import log_execution_time


class TradingEngine:
    """Orchestrates one full scan cycle: collect, score, detect changes,
    analyze changed stocks with Claude, report, email, and persist the snapshot.
    Contains all business logic - scheduler.py only decides *when* to call run()."""

    def __init__(
        self,
        collector: FinvizCollector,
        scorer: MomentumScorer,
        snapshot_manager: SnapshotManager,
        change_detector: ChangeDetector,
        claude_analyzer: ClaudeAnalyzer,
        report_generator: ReportGenerator,
        email_service: EmailService,
    ):
        self.collector = collector
        self.scorer = scorer
        self.snapshot_manager = snapshot_manager
        self.change_detector = change_detector
        self.claude_analyzer = claude_analyzer
        self.report_generator = report_generator
        self.email_service = email_service

    def run(self) -> None:
        with log_execution_time("Trading engine cycle"):
            self._run()

    def _run(self) -> None:
        try:
            stocks = self.collector.collect()
        except Exception as exc:
            logger.error(f"Finviz collection failed, skipping this cycle: {exc}")
            return

        if not stocks:
            logger.warning("No candidates returned by screener, skipping this cycle.")
            return

        scored = self.scorer.score_all(stocks)

        previous = self.snapshot_manager.load_latest()
        events = self.change_detector.detect(scored, previous)

        if not events:
            logger.info("No meaningful changes detected - no analysis, no email.")
            self.snapshot_manager.save(scored)
            return

        changed_stocks, change_reasons = self._select_changed(scored, events)

        try:
            analyzed = self.claude_analyzer.analyze(changed_stocks, change_reasons)
        except Exception as exc:
            logger.error(f"Claude analysis step failed: {exc}")
            analyzed = changed_stocks

        html_report = None
        try:
            html_report = self.report_generator.generate(scored, events, analyzed)
        except Exception as exc:
            logger.error(f"Report generation failed: {exc}")

        if html_report is not None:
            try:
                self.email_service.send(
                    subject=f"{len(events)} change(s) detected",
                    html_body=html_report,
                )
            except Exception as exc:
                logger.error(f"Email send failed: {exc}")

        self.snapshot_manager.save(scored)

    @staticmethod
    def _select_changed(scored, events):
        """Stocks worth sending to Claude: everything except tickers whose only
        change was leaving the Top N (they don't need a fresh 'why it ranks' write-up)."""

        by_ticker = {s.ticker: s for s in scored}

        reason_lists: dict[str, list[str]] = {}
        analysis_worthy: set[str] = set()

        for event in events:
            reason_lists.setdefault(event.ticker, []).append(event.description)
            if event.change_type != ChangeType.LEFT_TOP_N:
                analysis_worthy.add(event.ticker)

        changed_stocks = [by_ticker[t] for t in analysis_worthy if t in by_ticker]
        change_reasons = {t: " ".join(msgs) for t, msgs in reason_lists.items()}

        return changed_stocks, change_reasons
