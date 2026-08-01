from __future__ import annotations

from loguru import logger

from analysis.candidate_selector import CandidateSelector
from analysis.change_detector import ChangeDetector
from analysis.claude_analyzer import ClaudeAnalyzer
from analysis.conviction_scorer import ConvictionScorer
from analysis.enrichment_service import EnrichmentService
from analysis.fibonacci import FibonacciAnalyzer
from analysis.momentum_scorer import MomentumScorer
from analysis.news_validator import NewsValidator
from analysis.outcome_tracker import AlertOutcomeTracker
from browser.browser import Browser
from config.settings import Settings
from finviz.collector import FinvizCollector
from market_data.price_history_provider import PriceHistoryProvider
from notifications.email_service import EmailService
from reports.report_generator import ReportGenerator
from storage.snapshot_manager import SnapshotManager
from utils.timing import log_execution_time


class TradingEngine:
    """Orchestrates one full scan cycle: collect, score, detect changes,
    analyze changed stocks with Claude, report, email, and persist the snapshot.
    Contains all business logic - runner.py only decides *when* to call run()."""

    def __init__(
        self,
        collector: FinvizCollector,
        scorer: MomentumScorer,
        snapshot_manager: SnapshotManager,
        change_detector: ChangeDetector,
        candidate_selector: CandidateSelector,
        enrichment_service: EnrichmentService,
        claude_analyzer: ClaudeAnalyzer,
        conviction_scorer: ConvictionScorer,
        outcome_tracker: AlertOutcomeTracker,
        report_generator: ReportGenerator,
        email_service: EmailService,
    ):
        self.collector = collector
        self.scorer = scorer
        self.snapshot_manager = snapshot_manager
        self.change_detector = change_detector
        self.candidate_selector = candidate_selector
        self.enrichment_service = enrichment_service
        self.claude_analyzer = claude_analyzer
        self.conviction_scorer = conviction_scorer
        self.outcome_tracker = outcome_tracker
        self.report_generator = report_generator
        self.email_service = email_service

    @classmethod
    def from_settings(cls, settings: Settings) -> "TradingEngine":
        """Wires every component from a single Settings object - the composition root."""

        browser = Browser(
            profile_dir=settings.browser.profile_dir,
            headless=settings.browser.headless,
        )
        collector = FinvizCollector(
            browser=browser,
            screener_url=settings.finviz_screener_url,
            downloads_dir=settings.downloads_dir,
            download_timeout_ms=settings.browser.download_timeout_ms,
        )

        enrichment_service = EnrichmentService(
            browser=browser,
            price_history_provider=PriceHistoryProvider(),
            fibonacci_analyzer=FibonacciAnalyzer(),
            news_validator=NewsValidator(),
            fibonacci_lookback_days=settings.enrichment.fibonacci_lookback_days,
            news_max_headlines=settings.enrichment.news_max_headlines,
            news_fetch_delay_seconds=settings.enrichment.news_fetch_delay_seconds,
        )
        conviction_scorer = ConvictionScorer(settings.ranking_config_path)
        outcome_tracker = AlertOutcomeTracker(
            db_path=settings.outcomes_db_path,
            checkpoint_minutes=settings.outcome_tracking.checkpoint_minutes,
            price_provider=PriceHistoryProvider(),
            conviction_bucket_high=settings.outcome_tracking.conviction_bucket_high,
            conviction_bucket_medium=settings.outcome_tracking.conviction_bucket_medium,
        )

        return cls(
            collector=collector,
            scorer=MomentumScorer(settings.scoring_config_path),
            snapshot_manager=SnapshotManager(
                settings.snapshots.directory, settings.snapshots.retention_days
            ),
            change_detector=ChangeDetector(
                settings.change_detection, settings.snapshots.top_n
            ),
            candidate_selector=CandidateSelector(settings.analysis_config_path),
            enrichment_service=enrichment_service,
            claude_analyzer=ClaudeAnalyzer(
                settings.claude,
                settings.prompts_config_path,
                settings.enrichment.prompt_headline_count,
            ),
            conviction_scorer=conviction_scorer,
            outcome_tracker=outcome_tracker,
            report_generator=ReportGenerator(conviction_scorer),
            email_service=EmailService(settings.email),
        )

    def run(self) -> None:
        with log_execution_time("Trading engine cycle"):
            self._run()
            self._cleanup_old_snapshots()
            self._record_due_outcome_checkpoints()

    def _cleanup_old_snapshots(self) -> None:
        try:
            self.snapshot_manager.cleanup_old()
        except Exception as exc:
            logger.error(f"Snapshot cleanup failed: {exc}")

    def _record_due_outcome_checkpoints(self) -> None:
        try:
            self.outcome_tracker.record_due_checkpoints()
        except Exception as exc:
            logger.error(f"Outcome checkpoint recording failed: {exc}")

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

        if previous is None:
            candidates = self.candidate_selector.select(scored)
            logger.info(
                f"Initial scan - no previous snapshot. Establishing a baseline of "
                f"{len(scored)} stock(s); analyzing the top {len(candidates)} by "
                f"volume for the first report."
            )
            self._analyze_report_and_email(
                scored=scored,
                events=[],
                candidates=candidates,
                subject="Initial scan - baseline established",
            )
            self.snapshot_manager.save(scored)
            return

        events = self.change_detector.detect(scored, previous)

        if not events:
            logger.info("No meaningful changes detected - no analysis, no email.")
            self.snapshot_manager.save(scored)
            return

        candidates = self.candidate_selector.select(scored)

        self._analyze_report_and_email(
            scored=scored,
            events=events,
            candidates=candidates,
            subject=f"{len(events)} change(s) detected",
        )

        self.snapshot_manager.save(scored)

    def _analyze_report_and_email(
        self,
        scored,
        events,
        candidates,
        subject: str,
    ) -> None:
        selected_tickers = {s.ticker for s in candidates}
        not_analyzed = [s for s in scored if s.ticker not in selected_tickers]

        try:
            candidates = self.enrichment_service.enrich(candidates)
        except Exception as exc:
            logger.error(f"Enrichment step failed, continuing without it: {exc}")

        try:
            analyzed = self.claude_analyzer.analyze(candidates)
        except Exception as exc:
            logger.error(f"Claude analysis step failed: {exc}")
            analyzed = candidates

        try:
            ranked = self.conviction_scorer.rank(analyzed)
        except Exception as exc:
            logger.error(f"Conviction ranking failed, using unranked order: {exc}")
            ranked = analyzed

        self._log_outcome_signals(ranked)

        subject = self._build_subject(ranked, fallback=subject)

        html_report = None
        try:
            html_report = self.report_generator.generate(
                scored, events, ranked, not_analyzed
            )
        except Exception as exc:
            logger.error(f"Report generation failed: {exc}")

        if html_report is not None:
            try:
                self.email_service.send(subject=subject, html_body=html_report)
            except Exception as exc:
                logger.error(f"Email send failed: {exc}")

    def _log_outcome_signals(self, ranked) -> None:
        """Logs the Must-Watch subset as if it had alerted - Step 1 of the
        alerting tier, evidence for whether scoring/AI-analysis is any good,
        built before any live alert email exists."""

        must_watch = ranked[: self.conviction_scorer.must_watch_top_n]
        for stock in must_watch:
            try:
                conviction_score = self.conviction_scorer.score(stock)
                self.outcome_tracker.log_signal(stock, conviction_score)
            except Exception as exc:
                logger.error(f"Outcome signal logging failed for {stock.ticker}: {exc}")

    def _build_subject(self, ranked, fallback: str) -> str:
        """Reflects the top Must-Watch ticker(s) in the subject line, so the
        headline is skimmable before even opening the email."""

        top_tickers = [
            s.ticker for s in ranked[: self.conviction_scorer.must_watch_top_n]
        ]
        if not top_tickers:
            return fallback

        shown = top_tickers[:3]
        subject = f"Must-Watch: {', '.join(shown)}"
        remaining = len(top_tickers) - len(shown)
        if remaining > 0:
            subject += f" +{remaining} more"
        return subject
