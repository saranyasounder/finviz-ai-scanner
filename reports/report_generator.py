from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from analysis.conviction_scorer import ConvictionScorer
from models.change_event import ChangeEvent
from models.stock_candidate import StockCandidate

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


class ReportGenerator:
    """Renders the two-part HTML report: Part 1 is a compact table (one row
    per Must-Watch candidate - ticker, action, entry zone, stop, target,
    confidence, news alignment); Part 2 is one alert card per ranked
    candidate (action badge as the dominant visual element, confidence,
    entry/stop/target, reasoning), followed by a de-emphasized "Other
    Candidates" table for everything CandidateSelector didn't send to
    enrichment/AI this cycle - momentum score only, clearly labeled as not
    AI-analyzed. `analyzed` is expected to already be ordered by the caller
    (conviction score, highest first) - this class renders in whatever
    order it's given, it doesn't rank. ConvictionScorer is used only for
    must_watch_top_n here; the blended conviction score itself is not
    displayed - the schema's own confidence.score/grade is the visible
    signal now."""

    def __init__(self, conviction_scorer: ConvictionScorer):
        self.conviction_scorer = conviction_scorer
        self._env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=select_autoescape(["html", "jinja"]),
        )

    def generate(
        self,
        current: list[StockCandidate],
        events: list[ChangeEvent],
        analyzed: list[StockCandidate],
        not_analyzed: list[StockCandidate],
    ) -> str:
        must_watch = analyzed[: self.conviction_scorer.must_watch_top_n]

        template = self._env.get_template("report.html.jinja")

        return template.render(
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            market_summary=self._build_market_summary(current, events),
            must_watch=must_watch,
            full_analysis=analyzed,
            not_analyzed=sorted(not_analyzed, key=lambda s: s.score, reverse=True),
            risk_summary=self._build_risk_summary(current),
        )

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
