from __future__ import annotations

from pathlib import Path

import yaml
from loguru import logger

from models.stock_candidate import StockCandidate


class CandidateSelector:
    """Selects which of the full scanned universe are worth spending news/
    Fibonacci/AI-analysis credits on this cycle: highest raw share Volume
    first (a liquidity/fillability gate - can this actually be traded right
    now), not Relative Volume (a momentum/unusualness signal already
    captured separately by MomentumScorer).

    Replaces change-detection as the criterion for "who gets analyzed" - a
    hard, predictable cap of at most volume_top_n AI calls per triggering
    cycle, regardless of how many tickers technically changed. Candidates
    not selected still keep their deterministic momentum score and still
    appear in the report/snapshot - they just don't get the expensive
    treatment."""

    def __init__(self, analysis_config_path: Path):
        with analysis_config_path.open("r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        self.volume_top_n: int = config["volume_top_n"]

    def select(self, stocks: list[StockCandidate]) -> list[StockCandidate]:
        ranked_by_volume = sorted(stocks, key=lambda s: s.volume, reverse=True)

        logger.debug(
            "Full candidate list ranked by volume: "
            + ", ".join(f"{s.ticker}={s.volume}" for s in ranked_by_volume)
        )

        selected = ranked_by_volume[: self.volume_top_n]

        logger.info(
            f"Selected top {len(selected)} candidate(s) by volume for "
            f"news/Fibonacci/AI analysis: " + ", ".join(s.ticker for s in selected)
        )

        return selected
