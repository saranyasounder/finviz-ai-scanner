from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from models.stock_candidate import StockCandidate

_RULE_EVALUATORS = {
    "threshold_high_medium": lambda value, rule: (
        rule["high_score"]
        if value > rule["high"]
        else rule["medium_score"] if value > rule["medium"] else 0.0
    ),
    "threshold_single": lambda value, rule: (
        rule["score"] if value > rule["threshold"] else 0.0
    ),
    "range": lambda value, rule: (
        rule["score"] if rule["min"] <= value <= rule["max"] else 0.0
    ),
}


class MomentumScorer:
    """Config-driven momentum scoring engine. Rules live in config/scoring.yaml -
    adding a new scoring factor is a YAML edit, not a code change."""

    def __init__(self, scoring_config_path: Path):
        with scoring_config_path.open("r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        self.rules: dict[str, dict[str, Any]] = config.get("rules", {})

    def score(self, stock: StockCandidate) -> StockCandidate:
        total_score = 0.0
        breakdown: dict[str, float] = {}

        for rule_name, rule in self.rules.items():
            value = getattr(stock, rule["field"], None)
            if value is None:
                continue

            evaluator = _RULE_EVALUATORS.get(rule["type"])
            if evaluator is None:
                logger.warning(
                    f"Unknown scoring rule type '{rule['type']}' for '{rule_name}', skipping."
                )
                continue

            points = evaluator(value, rule)
            if points:
                total_score += points
                breakdown[rule_name] = points

        stock.score = total_score
        stock.score_breakdown = breakdown
        return stock

    def score_all(self, stocks: list[StockCandidate]) -> list[StockCandidate]:
        scored = [self.score(stock) for stock in stocks]
        scored.sort(key=lambda s: s.score, reverse=True)
        return scored
