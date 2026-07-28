from __future__ import annotations

from pathlib import Path

import yaml

from models.news_validation import NewsVerdict
from models.stock_candidate import StockCandidate


class ConvictionScorer:
    """Ranks stocks by likelihood of profit rather than raw momentum score alone:
    a weighted blend of the momentum score, the AI-analysis confidence rating,
    and the strongest news-verdict signal present. Weights live in
    config/ranking.yaml so they can be tuned without a code change."""

    def __init__(self, ranking_config_path: Path):
        with ranking_config_path.open("r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

        self.momentum_weight: float = config["weights"]["momentum"]
        self.ai_confidence_weight: float = config["weights"]["ai_confidence"]
        self.ai_confidence_scale: dict[str, float] = config["ai_confidence_scale"]
        self.news_verdict_modifiers: dict[str, float] = config["news_verdict_modifiers"]
        self.must_watch_top_n: int = config["must_watch_top_n"]

    def score(self, stock: StockCandidate) -> float:
        ai_confidence = self._ai_confidence_normalized(stock)
        news_modifier = self._news_verdict_modifier(stock)

        return (
            stock.score * self.momentum_weight
            + ai_confidence * self.ai_confidence_weight
            + news_modifier
        )

    def rank(self, stocks: list[StockCandidate]) -> list[StockCandidate]:
        return sorted(stocks, key=self.score, reverse=True)

    def _ai_confidence_normalized(self, stock: StockCandidate) -> float:
        default = self.ai_confidence_scale.get("default", 50)
        if stock.analysis is None:
            return default
        return self.ai_confidence_scale.get(stock.analysis.confidence, default)

    def _news_verdict_modifier(self, stock: StockCandidate) -> float:
        if not stock.news_validations:
            return self.news_verdict_modifiers.get("no_news", 0)

        verdicts = {v.verdict for v in stock.news_validations}

        if NewsVerdict.CONFLICTING in verdicts:
            return self.news_verdict_modifiers["conflicting"]
        if NewsVerdict.CORROBORATED in verdicts:
            return self.news_verdict_modifiers["corroborated"]
        return self.news_verdict_modifiers["inconclusive"]
