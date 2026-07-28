from datetime import datetime, timedelta

from analysis.outcome_tracker import AlertOutcomeTracker
from models.alert_signal import OutcomeStatus
from models.claude_analysis import ClaudeAnalysis
from models.stock_candidate import StockCandidate


class _StubPriceProvider:
    """Test double for PriceHistoryProvider - no network, caller controls prices."""

    def __init__(self, prices: dict[str, float]):
        self.prices = prices
        self.calls: list[list[str]] = []

    def get_current_prices_many(self, tickers: list[str]) -> dict[str, float]:
        self.calls.append(list(tickers))
        return {t: self.prices[t] for t in tickers if t in self.prices}


def _stock(
    ticker: str,
    price: float,
    entry: float | None = None,
    stop: float | None = None,
    target: float | None = None,
    confidence: str = "Medium",
) -> StockCandidate:
    analysis = None
    if entry is not None:
        analysis = ClaudeAnalysis(
            reasoning="r",
            risk="r",
            entry=str(entry),
            stop_loss=str(stop),
            profit_target=str(target),
            confidence=confidence,
            trade_quality="B",
            entry_price=entry,
            stop_loss_price=stop,
            profit_target_price=target,
        )

    return StockCandidate(
        ticker=ticker,
        company=f"{ticker} Corp",
        sector="Technology",
        industry="Software",
        country="USA",
        price=price,
        change=1.0,
        volume=1_000_000,
        analysis=analysis,
    )


def _tracker(
    tmp_path, prices: dict[str, float] | None = None
) -> tuple[AlertOutcomeTracker, _StubPriceProvider]:
    provider = _StubPriceProvider(prices or {})
    tracker = AlertOutcomeTracker(
        db_path=tmp_path / "outcomes.db",
        checkpoint_minutes=[30, 60],
        price_provider=provider,
        conviction_bucket_high=70,
        conviction_bucket_medium=40,
    )
    return tracker, provider


def test_log_signal_creates_signal_and_one_checkpoint_per_interval(tmp_path):
    tracker, _ = _tracker(tmp_path)
    stock = _stock("AAA", price=50.0, entry=50.0, stop=48.0, target=55.0)

    signal_id = tracker.log_signal(stock, conviction_score=75.0)

    with tracker._connect() as conn:
        signal = conn.execute(
            "SELECT * FROM signals WHERE id = ?", (signal_id,)
        ).fetchone()
        checkpoints = conn.execute(
            "SELECT * FROM checkpoints WHERE signal_id = ?", (signal_id,)
        ).fetchall()

    assert signal["ticker"] == "AAA"
    assert signal["conviction_score"] == 75.0
    assert signal["entry_price"] == 50.0
    assert len(checkpoints) == 2
    assert {c["label"] for c in checkpoints} == {"+30min", "+1hr"}
    assert all(c["recorded_at"] is None for c in checkpoints)


def test_record_due_checkpoints_only_updates_due_ones(tmp_path):
    tracker, provider = _tracker(tmp_path, prices={"AAA": 53.0})
    stock = _stock("AAA", price=50.0, entry=50.0, stop=48.0, target=55.0)
    signaled_at = datetime(2026, 1, 1, 10, 0)

    tracker.log_signal(stock, conviction_score=75.0, signaled_at=signaled_at)

    # Only the +30min checkpoint (due at 10:30) is due by 10:31; +1hr (due 11:00) isn't yet.
    recorded = tracker.record_due_checkpoints(now=signaled_at + timedelta(minutes=31))

    assert recorded == 1
    with tracker._connect() as conn:
        checkpoints = conn.execute("SELECT * FROM checkpoints").fetchall()
    recorded_labels = {c["label"] for c in checkpoints if c["recorded_at"] is not None}
    pending_labels = {c["label"] for c in checkpoints if c["recorded_at"] is None}
    assert recorded_labels == {"+30min"}
    assert pending_labels == {"+1hr"}


def test_missing_price_leaves_checkpoint_pending(tmp_path):
    tracker, _ = _tracker(tmp_path, prices={})  # no price available for AAA
    stock = _stock("AAA", price=50.0, entry=50.0, stop=48.0, target=55.0)
    signaled_at = datetime(2026, 1, 1, 10, 0)

    tracker.log_signal(stock, conviction_score=75.0, signaled_at=signaled_at)
    recorded = tracker.record_due_checkpoints(now=signaled_at + timedelta(hours=2))

    assert recorded == 0


def test_report_classifies_win_when_price_reaches_target(tmp_path):
    tracker, _ = _tracker(tmp_path, prices={"AAA": 56.0})
    stock = _stock("AAA", price=50.0, entry=50.0, stop=48.0, target=55.0)
    signaled_at = datetime(2026, 1, 1, 10, 0)

    tracker.log_signal(stock, conviction_score=75.0, signaled_at=signaled_at)
    tracker.record_due_checkpoints(now=signaled_at + timedelta(hours=2))

    report = tracker.build_report()

    assert report.wins == 1
    assert report.losses == 0
    assert report.entries[0].status == OutcomeStatus.WIN


def test_report_classifies_loss_when_price_reaches_stop(tmp_path):
    tracker, _ = _tracker(tmp_path, prices={"AAA": 47.0})
    stock = _stock("AAA", price=50.0, entry=50.0, stop=48.0, target=55.0)
    signaled_at = datetime(2026, 1, 1, 10, 0)

    tracker.log_signal(stock, conviction_score=75.0, signaled_at=signaled_at)
    tracker.record_due_checkpoints(now=signaled_at + timedelta(hours=2))

    report = tracker.build_report()

    assert report.losses == 1
    assert report.entries[0].status == OutcomeStatus.LOSS


def test_report_pending_when_no_checkpoint_recorded_yet(tmp_path):
    tracker, _ = _tracker(tmp_path, prices={"AAA": 53.0})
    stock = _stock("AAA", price=50.0, entry=50.0, stop=48.0, target=55.0)
    tracker.log_signal(stock, conviction_score=75.0)

    report = tracker.build_report()

    assert report.pending == 1
    assert report.entries[0].status == OutcomeStatus.PENDING


def test_report_pending_when_missing_numeric_levels(tmp_path):
    tracker, _ = _tracker(tmp_path, prices={"AAA": 53.0})
    stock = _stock("AAA", price=50.0)  # no analysis at all -> no numeric levels
    signaled_at = datetime(2026, 1, 1, 10, 0)

    tracker.log_signal(stock, conviction_score=75.0, signaled_at=signaled_at)
    tracker.record_due_checkpoints(now=signaled_at + timedelta(hours=2))

    report = tracker.build_report()

    assert report.entries[0].status == OutcomeStatus.PENDING


def test_average_move_pct_computed_across_recorded_signals(tmp_path):
    tracker, _ = _tracker(tmp_path, prices={"AAA": 55.0, "BBB": 45.0})
    signaled_at = datetime(2026, 1, 1, 10, 0)

    tracker.log_signal(
        _stock("AAA", price=50.0, entry=50.0, stop=48.0, target=60.0),
        conviction_score=80.0,
        signaled_at=signaled_at,
    )
    tracker.log_signal(
        _stock("BBB", price=50.0, entry=50.0, stop=48.0, target=60.0),
        conviction_score=30.0,
        signaled_at=signaled_at,
    )
    tracker.record_due_checkpoints(now=signaled_at + timedelta(hours=2))

    report = tracker.build_report()

    # AAA: +10%, BBB: -10% -> average 0%
    assert report.average_move_pct == 0.0


def test_conviction_buckets_partition_correctly(tmp_path):
    tracker, _ = _tracker(tmp_path, prices={})
    tracker.log_signal(_stock("HIGH", price=10.0), conviction_score=80.0)
    tracker.log_signal(_stock("MED", price=10.0), conviction_score=50.0)
    tracker.log_signal(_stock("LOW", price=10.0), conviction_score=20.0)

    report = tracker.build_report()

    bucket_totals = {b.bucket: b.total for b in report.buckets}
    assert sum(bucket_totals.values()) == 3
    high_bucket = next(b for b in report.buckets if b.bucket.startswith("High"))
    low_bucket = next(b for b in report.buckets if b.bucket.startswith("Low"))
    assert high_bucket.total == 1
    assert low_bucket.total == 1
