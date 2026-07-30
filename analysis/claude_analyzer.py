from __future__ import annotations

import json
import re
from pathlib import Path

import yaml
from loguru import logger
from openai import APIStatusError, OpenAI

from config.settings import ClaudeSettings
from models.claude_analysis import ClaudeAnalysis
from models.stock_candidate import StockCandidate

_JSON_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class ClaudeAnalyzer:
    """Sends only changed/top-ranked stocks to Claude for trade analysis.
    Claude never receives the raw screener CSV - only the already-scored,
    already-filtered StockCandidate fields relevant to a trade decision.

    Below min_score_to_analyze, a stock skips the API call entirely (it still
    keeps its score/news/Fibonacci data, just no AI writeup) - a cost control
    for accounts on a tight OpenRouter budget. On a 402 (out of credits), the
    whole remaining batch is abandoned rather than retried per-ticker, since
    it's an account-level condition that won't resolve mid-cycle.

    Routed through OpenRouter's OpenAI-compatible API rather than Anthropic's
    native API, since that's the key/provider configured for this project."""

    def __init__(
        self,
        claude_settings: ClaudeSettings,
        prompts_path: Path,
        prompt_headline_count: int = 3,
    ):
        self.settings = claude_settings
        self.prompt_headline_count = prompt_headline_count
        self.client = OpenAI(
            base_url=claude_settings.base_url,
            api_key=claude_settings.api_key,
            timeout=claude_settings.request_timeout_seconds,
        )

        with prompts_path.open("r", encoding="utf-8") as f:
            prompts = yaml.safe_load(f) or {}
        self.system_prompt: str = prompts["system"]
        self.user_template: str = prompts["user_template"]

    def analyze(
        self, stocks: list[StockCandidate], change_reasons: dict[str, str]
    ) -> list[StockCandidate]:
        skipped_low_score = 0

        for index, stock in enumerate(stocks):
            if stock.score < self.settings.min_score_to_analyze:
                skipped_low_score += 1
                continue

            try:
                stock.analysis = self._analyze_one(
                    stock, change_reasons.get(stock.ticker, "")
                )
            except APIStatusError as exc:
                if exc.status_code == 402:
                    remaining = len(stocks) - index
                    logger.error(
                        f"OpenRouter is out of credits (402) - skipping AI analysis "
                        f"for the remaining {remaining} candidate(s) this cycle. Add "
                        f"credits at https://openrouter.ai/settings/credits."
                    )
                    break
                logger.error(f"Claude analysis failed for {stock.ticker}: {exc}")
            except Exception as exc:
                logger.error(f"Claude analysis failed for {stock.ticker}: {exc}")

        if skipped_low_score:
            logger.info(
                f"Skipped AI analysis for {skipped_low_score} candidate(s) below "
                f"the momentum-score threshold ({self.settings.min_score_to_analyze})."
            )

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
            change_reason=change_reason,
            news_section=self._build_news_section(stock),
            fibonacci_section=self._build_fibonacci_section(stock),
        )

        logger.debug(f"Requesting Claude analysis for {stock.ticker} via OpenRouter")

        response = self.client.chat.completions.create(
            model=self.settings.model,
            max_tokens=self.settings.max_tokens,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            extra_headers={
                "HTTP-Referer": self.settings.site_url,
                "X-Title": self.settings.site_name,
            },
        )

        content = response.choices[0].message.content
        data = json.loads(_JSON_FENCE.sub("", content.strip()))
        return ClaudeAnalysis(**data)

    def _build_news_section(self, stock: StockCandidate) -> str:
        if not stock.news_items:
            return "No recent news available."

        pairs = list(zip(stock.news_items, stock.news_validations))[
            : self.prompt_headline_count
        ]

        lines = [
            f'- "{item.headline}" ({item.source or "unknown source"}) - '
            f"{validation.verdict.value.upper()}: {validation.note}"
            for item, validation in pairs
        ]
        return "\n  ".join(lines)

    @staticmethod
    def _build_fibonacci_section(stock: StockCandidate) -> str:
        fib = stock.fibonacci
        if fib is None:
            return "No Fibonacci data available."

        return (
            f"Trend: {fib.trend.value}. Swing High: {fib.swing_high:.2f}, "
            f"Swing Low: {fib.swing_low:.2f}. Nearest Support: {fib.nearest_support}, "
            f"Nearest Resistance: {fib.nearest_resistance}."
        )
