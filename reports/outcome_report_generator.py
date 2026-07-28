from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from models.outcome_report import OutcomeReport

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


class OutcomeReportGenerator:
    """Renders AlertOutcomeTracker's OutcomeReport as HTML (using the shared
    mobile-readable data table) or as a plain-text CLI summary."""

    def __init__(self):
        self._env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=select_autoescape(["html", "jinja"]),
        )

    def generate_html(self, report: OutcomeReport) -> str:
        template = self._env.get_template("outcome_report.html.jinja")

        bucket_rows = [
            [
                bucket.bucket,
                str(bucket.total),
                str(bucket.wins),
                str(bucket.losses),
                str(bucket.pending),
                (
                    f"{bucket.hit_rate_pct:.1f}%"
                    if bucket.hit_rate_pct is not None
                    else "n/a"
                ),
            ]
            for bucket in report.buckets
        ]

        entry_rows = [
            [
                entry.ticker,
                entry.signaled_at.strftime("%Y-%m-%d %H:%M"),
                f"{entry.conviction_score:.1f}",
                entry.status.value.upper(),
                f"{entry.move_pct:+.2f}%" if entry.move_pct is not None else "n/a",
                entry.latest_checkpoint_label or "n/a",
            ]
            for entry in report.entries
        ]

        return template.render(
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            report=report,
            bucket_rows=bucket_rows,
            entry_rows=entry_rows,
        )

    def generate_text_summary(self, report: OutcomeReport) -> str:
        hit_rate = (
            f"{report.hit_rate_pct:.1f}%" if report.hit_rate_pct is not None else "n/a"
        )
        avg_move = (
            f"{report.average_move_pct:+.2f}%"
            if report.average_move_pct is not None
            else "n/a"
        )

        lines = [
            f"Total signals: {report.total_signals}",
            f"Wins: {report.wins}  Losses: {report.losses}  Pending: {report.pending}",
            f"Hit rate (decided only): {hit_rate}",
            f"Average move: {avg_move}",
            "",
            "By conviction bucket:",
        ]

        for bucket in report.buckets:
            rate = (
                f"{bucket.hit_rate_pct:.1f}%"
                if bucket.hit_rate_pct is not None
                else "n/a"
            )
            lines.append(
                f"  {bucket.bucket}: {bucket.total} signal(s) "
                f"({bucket.wins}W/{bucket.losses}L/{bucket.pending}P), hit rate {rate}"
            )

        return "\n".join(lines)
