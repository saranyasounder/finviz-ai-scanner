from __future__ import annotations

import json
from pathlib import Path

import yaml
from anthropic import Anthropic
from loguru import logger

from config.settings import ClaudeSettings
from models.claude_analysis import ClaudeAnalysis
from models.stock_candidate import StockCandidate


class ClaudeAnalyzer:
    """Sends only changed/top-ranked stocks to Claude for trade analysis.
    Claude never receives the raw screener CSV - only the already-scored,
    already-filtered StockCandidate fields relevant to a trade decision."""

    def __init__(self, claude_settings: ClaudeSettings, prompts_path: Path):
        self.settings = claude_settings
        self.client = Anthropic(api_key=claude_settings.api_key)

        with prompts_path.open("r", encoding="utf-8") as f:
            prompts = yaml.safe_load(f) or {}
        self.system_prompt: str = prompts["system"]
        self.user_template: str = prompts["user_template"]

    def analyze(
        self, stocks: list[StockCandidate], change_reasons: dict[str, str]
    ) -> list[StockCandidate]:
        for stock in stocks:
            try:
                stock.analysis = self._analyze_one(
                    stock, change_reasons.get(stock.ticker, "")
                )
            except Exception as exc:
                logger.error(f"Claude analysis failed for {stock.ticker}: {exc}")
        return stocks

    def _analyze_one(self, stock: StockCandidate, change_reason: str) -> ClaudeAnalysis:
        prompt = self.user_template.format(
            ticker=stock.ticker,
            company=stock.company,
            sector=stock.sector,
            industry=stock.industry,
            price=stock.price,
            gap=stock.gap,
            relative_volume=stock.relative_volume,
            atr=stock.atr,
            rsi=stock.rsi,
            sma20=stock.sma20,
            sma50=stock.sma50,
            beta=stock.beta,
            short_float=stock.short_float,
            institutional_ownership=stock.institutional_ownership,
            score=stock.score,
            score_breakdown=stock.score_breakdown,
            change_reason=change_reason,
        )

        logger.debug(f"Requesting Claude analysis for {stock.ticker}")

        response = self.client.messages.create(
            model=self.settings.model,
            max_tokens=self.settings.max_tokens,
            system=self.system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )

        data = json.loads(response.content[0].text)
        return ClaudeAnalysis(**data)
