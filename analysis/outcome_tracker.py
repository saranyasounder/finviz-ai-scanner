"""Step 1 of the alerting tier: log every candidate that crosses the
"would have alerted" threshold (today, that's the Must-Watch list) and check
back on it at configured intervals, so there's real evidence of whether the
scoring/AI-analysis is any good before a single live alert email exists."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from loguru import logger

from analysis.conviction_scorer import ConvictionScorer
from market_data.price_history_provider import PriceHistoryProvider
from models.alert_signal import OutcomeStatus
from models.outcome_report import ConvictionBucketStat, OutcomeEntry, OutcomeReport
from models.stock_candidate import StockCandidate

_SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    signaled_at TEXT NOT NULL,
    price_at_signal REAL NOT NULL,
    ai_confidence TEXT,
    conviction_score REAL NOT NULL,
    entry_price REAL,
    stop_loss_price REAL,
    profit_target_price REAL,
    news_verdict TEXT
);

CREATE TABLE IF NOT EXISTS checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id INTEGER NOT NULL REFERENCES signals(id),
    label TEXT NOT NULL,
    due_at TEXT NOT NULL,
    recorded_at TEXT,
    recorded_price REAL
);
"""


def _format_label(minutes: int) -> str:
    if minutes % 1440 == 0:
        return (
            f"+{minutes // 1440}day" if minutes == 1440 else f"+{minutes // 1440}days"
        )
    if minutes % 60 == 0:
        return f"+{minutes // 60}hr"
    return f"+{minutes}min"


class AlertOutcomeTracker:
    """Persists signals and their follow-up checkpoints in SQLite - chosen over
    flat JSON files because this needs to *update* existing records at future
    checkpoints and run aggregate queries (hit rate, averages), not just append
    immutable snapshots."""

    def __init__(
        self,
        db_path: Path,
        checkpoint_minutes: list[int],
        price_provider: PriceHistoryProvider,
        conviction_bucket_high: float,
        conviction_bucket_medium: float,
    ):
        self.db_path = db_path
        self.checkpoint_minutes = checkpoint_minutes
        self.price_provider = price_provider
        self.conviction_bucket_high = conviction_bucket_high
        self.conviction_bucket_medium = conviction_bucket_medium

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def log_signal(
        self,
        stock: StockCandidate,
        conviction_score: float,
        signaled_at: Optional[datetime] = None,
    ) -> int:
        signaled_at = signaled_at or datetime.now()
        analysis = stock.analysis
        worst_verdict = ConvictionScorer.worst_verdict(stock)

        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO signals (ticker, signaled_at, price_at_signal, ai_confidence, "
                "conviction_score, entry_price, stop_loss_price, profit_target_price, "
                "news_verdict) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    stock.ticker,
                    signaled_at.isoformat(),
                    stock.price,
                    analysis.confidence.grade.value if analysis else None,
                    conviction_score,
                    analysis.entry_zone.anchor_price if analysis else None,
                    analysis.stop_loss if analysis else None,
                    analysis.target.price if analysis else None,
                    worst_verdict.value if worst_verdict else None,
                ),
            )
            signal_id = cursor.lastrowid

            for minutes in self.checkpoint_minutes:
                due_at = signaled_at + timedelta(minutes=minutes)
                conn.execute(
                    "INSERT INTO checkpoints (signal_id, label, due_at) VALUES (?, ?, ?)",
                    (signal_id, _format_label(minutes), due_at.isoformat()),
                )

        logger.info(
            f"Logged outcome-tracking signal for {stock.ticker} "
            f"(id={signal_id}, conviction={conviction_score:.1f})"
        )
        return signal_id

    def record_due_checkpoints(self, now: Optional[datetime] = None) -> int:
        now = now or datetime.now()

        with self._connect() as conn:
            due_rows = conn.execute(
                "SELECT checkpoints.id AS checkpoint_id, signals.ticker AS ticker "
                "FROM checkpoints JOIN signals ON signals.id = checkpoints.signal_id "
                "WHERE checkpoints.due_at <= ? AND checkpoints.recorded_at IS NULL",
                (now.isoformat(),),
            ).fetchall()

        if not due_rows:
            return 0

        tickers = sorted({row["ticker"] for row in due_rows})
        prices = self.price_provider.get_current_prices_many(tickers)

        recorded = 0
        with self._connect() as conn:
            for row in due_rows:
                price = prices.get(row["ticker"])
                if price is None:
                    logger.warning(
                        f"No current price for {row['ticker']}, "
                        f"checkpoint {row['checkpoint_id']} stays pending"
                    )
                    continue

                conn.execute(
                    "UPDATE checkpoints SET recorded_at = ?, recorded_price = ? WHERE id = ?",
                    (now.isoformat(), price, row["checkpoint_id"]),
                )
                recorded += 1

        if recorded:
            logger.info(f"Recorded {recorded} due outcome checkpoint(s).")

        return recorded

    def build_report(self) -> OutcomeReport:
        with self._connect() as conn:
            signals = conn.execute("SELECT * FROM signals").fetchall()
            recorded_checkpoints = conn.execute(
                "SELECT * FROM checkpoints WHERE recorded_at IS NOT NULL "
                "ORDER BY recorded_at ASC"
            ).fetchall()

        checkpoints_by_signal: dict[int, list[sqlite3.Row]] = {}
        for row in recorded_checkpoints:
            checkpoints_by_signal.setdefault(row["signal_id"], []).append(row)

        entries: list[OutcomeEntry] = []
        for signal in signals:
            latest = None
            for checkpoint in checkpoints_by_signal.get(signal["id"], []):
                latest = checkpoint  # last one wins, since the query is ordered ASC

            status = self._classify(signal, latest)
            move_pct = None
            if latest is not None and signal["price_at_signal"]:
                move_pct = (
                    (latest["recorded_price"] - signal["price_at_signal"])
                    / signal["price_at_signal"]
                    * 100
                )

            entries.append(
                OutcomeEntry(
                    ticker=signal["ticker"],
                    signaled_at=datetime.fromisoformat(signal["signaled_at"]),
                    conviction_score=signal["conviction_score"],
                    status=status,
                    move_pct=move_pct,
                    latest_checkpoint_label=latest["label"] if latest else None,
                )
            )

        return self._build_report_from_entries(entries)

    def _classify(
        self, signal: sqlite3.Row, latest_checkpoint: Optional[sqlite3.Row]
    ) -> OutcomeStatus:
        if latest_checkpoint is None:
            return OutcomeStatus.PENDING

        entry = signal["entry_price"]
        stop = signal["stop_loss_price"]
        target = signal["profit_target_price"]

        if entry is None or stop is None or target is None:
            return OutcomeStatus.PENDING

        price = latest_checkpoint["recorded_price"]
        bullish = target >= entry

        if bullish:
            if price >= target:
                return OutcomeStatus.WIN
            if price <= stop:
                return OutcomeStatus.LOSS
        else:
            if price <= target:
                return OutcomeStatus.WIN
            if price >= stop:
                return OutcomeStatus.LOSS

        return OutcomeStatus.PENDING

    def _build_report_from_entries(self, entries: list[OutcomeEntry]) -> OutcomeReport:
        wins = sum(1 for e in entries if e.status == OutcomeStatus.WIN)
        losses = sum(1 for e in entries if e.status == OutcomeStatus.LOSS)
        pending = sum(1 for e in entries if e.status == OutcomeStatus.PENDING)

        moves = [e.move_pct for e in entries if e.move_pct is not None]
        average_move_pct = sum(moves) / len(moves) if moves else None

        buckets = [
            self._bucket_stat(
                "High (>= " + f"{self.conviction_bucket_high:.0f})",
                entries,
                lambda s: s >= self.conviction_bucket_high,
            ),
            self._bucket_stat(
                f"Medium ({self.conviction_bucket_medium:.0f}-{self.conviction_bucket_high:.0f})",
                entries,
                lambda s: self.conviction_bucket_medium
                <= s
                < self.conviction_bucket_high,
            ),
            self._bucket_stat(
                "Low (< " + f"{self.conviction_bucket_medium:.0f})",
                entries,
                lambda s: s < self.conviction_bucket_medium,
            ),
        ]

        return OutcomeReport(
            entries=entries,
            total_signals=len(entries),
            wins=wins,
            losses=losses,
            pending=pending,
            average_move_pct=average_move_pct,
            buckets=buckets,
        )

    @staticmethod
    def _bucket_stat(
        label: str, entries: list[OutcomeEntry], predicate
    ) -> ConvictionBucketStat:
        bucket_entries = [e for e in entries if predicate(e.conviction_score)]
        return ConvictionBucketStat(
            bucket=label,
            total=len(bucket_entries),
            wins=sum(1 for e in bucket_entries if e.status == OutcomeStatus.WIN),
            losses=sum(1 for e in bucket_entries if e.status == OutcomeStatus.LOSS),
            pending=sum(1 for e in bucket_entries if e.status == OutcomeStatus.PENDING),
        )


def _main() -> None:
    """CLI: python -m analysis.outcome_tracker [--html path/to/report.html]"""

    import argparse

    from config.settings import load_settings
    from reports.outcome_report_generator import OutcomeReportGenerator

    parser = argparse.ArgumentParser(description="Alert outcome tracking report.")
    parser.add_argument(
        "--html",
        type=Path,
        default=None,
        help="Also write the HTML report to this path.",
    )
    args = parser.parse_args()

    settings = load_settings()
    tracker = AlertOutcomeTracker(
        db_path=settings.outcomes_db_path,
        checkpoint_minutes=settings.outcome_tracking.checkpoint_minutes,
        price_provider=PriceHistoryProvider(),
        conviction_bucket_high=settings.outcome_tracking.conviction_bucket_high,
        conviction_bucket_medium=settings.outcome_tracking.conviction_bucket_medium,
    )

    report = tracker.build_report()
    generator = OutcomeReportGenerator()

    print(generator.generate_text_summary(report))

    if args.html:
        args.html.write_text(generator.generate_html(report), encoding="utf-8")
        print(f"\nHTML report written to {args.html}")


if __name__ == "__main__":
    _main()
