from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from analysis.conviction_scorer import ConvictionScorer
from models.change_event import ChangeEvent
from models.stock_candidate import StockCandidate

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

_FIRST_SENTENCE = re.compile(r"(.+?\.)(\s|$)")


class ReportGenerator:
    """Renders the two-part HTML report: Must-Watch (compact, top N by
    conviction) and Full Analysis (every ranked candidate, full detail,
    conviction score as the primary scannable signal). `analyzed` is expected
    to already be ordered by the caller (conviction score, highest first) -
    this class renders in whatever order it's given, it doesn't rank."""

    def __init__(
        self,
        conviction_scorer: ConvictionScorer,
        conviction_bucket_high: float,
        conviction_bucket_medium: float,
    ):
        self.conviction_scorer = conviction_scorer
        self.conviction_bucket_high = conviction_bucket_high
        self.conviction_bucket_medium = conviction_bucket_medium
        self._env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=select_autoescape(["html", "jinja"]),
        )
        self._env.globals["zip"] = zip

    def generate(
        self,
        current: list[StockCandidate],
        events: list[ChangeEvent],
        analyzed: list[StockCandidate],
    ) -> str:
        reason_lists: dict[str, list[str]] = {}
        for event in events:
            reason_lists.setdefault(event.ticker, []).append(event.description)
        change_reasons = {t: " ".join(msgs) for t, msgs in reason_lists.items()}

        must_watch = analyzed[: self.conviction_scorer.must_watch_top_n]
        must_watch_reasons = {s.ticker: self._one_line_reason(s) for s in must_watch}

        conviction = {s.ticker: self._conviction_context(s) for s in analyzed}

        template = self._env.get_template("report.html.jinja")

        return template.render(
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            market_summary=self._build_market_summary(current, events),
            must_watch=must_watch,
            must_watch_reasons=must_watch_reasons,
            full_analysis=analyzed,
            change_reasons=change_reasons,
            conviction=conviction,
            risk_summary=self._build_risk_summary(current),
        )

    def _conviction_context(self, stock: StockCandidate) -> dict:
        score = self.conviction_scorer.score(stock)

        if score >= self.conviction_bucket_high:
            tier = "high"
        elif score >= self.conviction_bucket_medium:
            tier = "medium"
        else:
            tier = "low"

        return {"score": score, "tier": tier, "pct": max(0.0, min(100.0, score))}

    @staticmethod
    def _one_line_reason(stock: StockCandidate) -> str:
        if stock.analysis is None:
            return "Momentum candidate - AI analysis unavailable this scan."

        reasoning = stock.analysis.reasoning.strip()
        match = _FIRST_SENTENCE.match(reasoning)
        return match.group(1) if match else reasoning

    def _build_market_summary(
        self, current: list[StockCandidate], events: list[ChangeEvent]
    ) -> str:
        if not current:
            return "No candidates returned by the screener this scan."

        avg_score = sum(s.score for s in current) / len(current)
        return (
            f"{len(current)} candidates scanned, average momentum score {avg_score:.1f}. "
            f"{len(events)} meaningful change(s) detected this scan."
        )

    def _build_risk_summary(self, current: list[StockCandidate]) -> str:
        high_beta = [s for s in current if s.beta and s.beta > 1.5]
        high_short = [s for s in current if s.short_float and s.short_float > 10]
        return (
            f"{len(high_beta)} candidate(s) with beta > 1.5. "
            f"{len(high_short)} candidate(s) with short float > 10%. "
            "Position size accordingly and always use a stop loss."
        )
