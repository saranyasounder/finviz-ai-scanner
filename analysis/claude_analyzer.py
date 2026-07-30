from __future__ import annotations

import json
import re
from pathlib import Path

import yaml
from anthropic import Anthropic, APIStatusError
from loguru import logger

from config.settings import ClaudeSettings
from models.claude_analysis import ClaudeAnalysis
from models.stock_candidate import StockCandidate

_JSON_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
_CREDIT_ERROR_MARKER = "credit balance"


class ClaudeAnalyzer:
    """Sends only changed/top-ranked stocks to Claude for a real-time intraday
    trading decision - not research. Claude never receives the raw screener
    CSV, only the already-scored, already-filtered StockCandidate fields
    relevant to "what should I do right now."

    Below min_score_to_analyze, a stock skips the API call entirely (it still
    keeps its score/news/Fibonacci data, just no AI decision) - a cost control
    for accounts on a tight budget. On an insufficient-credit-balance error,
    the whole remaining batch is abandoned rather than retried per-ticker,
    since it's an account-level condition that won't resolve mid-cycle.

    Uses Anthropic's native Messages API (CLAUDE_API_KEY in .env) directly -
    not OpenRouter. JSON compliance is enforced via prompt instruction +
    strict Pydantic parsing (a response missing/nulling a field raises and is
    caught like any other analysis failure), not a schema-enforcing API
    parameter - this has already proven reliable for this model."""

    def __init__(
        self,
        claude_settings: ClaudeSettings,
        prompts_path: Path,
        prompt_headline_count: int = 3,
    ):
        self.settings = claude_settings
        self.prompt_headline_count = prompt_headline_count
        self.client = Anthropic(
            api_key=claude_settings.api_key,
            timeout=claude_settings.request_timeout_seconds,
        )

        with prompts_path.open("r", encoding="utf-8") as f:
            prompts = yaml.safe_load(f) or {}
        self.system_prompt: str = prompts["system"]
        self.user_template: str = prompts["user_template"]

    def analyze(self, stocks: list[StockCandidate]) -> list[StockCandidate]:
        skipped_low_score = 0

        for index, stock in enumerate(stocks):
            if stock.score < self.settings.min_score_to_analyze:
                skipped_low_score += 1
                continue

            try:
                stock.analysis = self._analyze_one(stock)
            except APIStatusError as exc:
                if _CREDIT_ERROR_MARKER in str(exc).lower():
                    remaining = len(stocks) - index
                    logger.error(
                        f"Anthropic account credit balance is too low - skipping AI "
                        f"analysis for the remaining {remaining} candidate(s) this "
                        f"cycle. Add credits at https://console.anthropic.com/settings/billing."
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

    def _analyze_one(self, stock: StockCandidate) -> ClaudeAnalysis:
        prompt = self.user_template.format(
            current_price=stock.price,
            current_volume=stock.volume,
            relative_volume=stock.relative_volume,
            market_state_section=self._build_market_state_section(stock),
            news_section=self._build_news_section(stock),
        )

        logger.debug(f"Requesting Claude analysis for {stock.ticker}")

        # temperature is deliberately not passed: confirmed live that
        # claude-sonnet-5 rejects it outright ("`temperature` is deprecated
        # for this model", 400) rather than silently ignoring it. The
        # settings.claude.temperature config value is kept for a future model
        # that does support it - not currently sent.
        response = self.client.messages.create(
            model=self.settings.model,
            max_tokens=self.settings.max_tokens,
            system=self.system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )

        content = self._extract_text(response)
        data = json.loads(_JSON_FENCE.sub("", content.strip()))
        return ClaudeAnalysis(**data)

    @staticmethod
    def _extract_text(response) -> str:
        """response.content[0] isn't reliably the text block - confirmed live
        that claude-sonnet-5 prepends a ThinkingBlock (extended thinking)
        before the actual TextBlock, so the text block has to be found by
        type rather than assumed to be first."""

        for block in response.content:
            if block.type == "text":
                return block.text
        raise ValueError("Claude response contained no text block")

    @staticmethod
    def _build_market_state_section(stock: StockCandidate) -> str:
        """Fibonacci support/resistance/trend, whenever enrichment produced
        them. day_high/day_low/VWAP/opening-range are deliberately absent -
        this pipeline has no intraday OHLC data source (Finviz's screener
        export is end-of-day, not tick data), and the system prompt itself
        forbids inventing data that wasn't supplied."""

        fib = stock.fibonacci
        if fib is None or fib.nearest_support is None:
            return (
                "Nearest Fibonacci Support: not available.\n"
                "Nearest Fibonacci Resistance: not available.\n"
                "Trend: unknown.\n"
                "No Fibonacci data available for this ticker - estimate the "
                "entry zone if recommending entry."
            )

        distance_support_pct = (
            (stock.price - fib.nearest_support) / fib.nearest_support * 100
        )

        lines = [
            f"Nearest Fibonacci Support: {fib.nearest_support:.2f}",
            f"Distance From Support: {distance_support_pct:+.2f}%",
        ]

        if fib.nearest_resistance is not None:
            distance_resistance_pct = (
                (fib.nearest_resistance - stock.price) / stock.price * 100
            )
            lines.append(f"Nearest Fibonacci Resistance: {fib.nearest_resistance:.2f}")
            lines.append(f"Distance From Resistance: {distance_resistance_pct:+.2f}%")

        lines.append(f"Trend: {fib.trend.value}")
        return "\n".join(lines)

    def _build_news_section(self, stock: StockCandidate) -> str:
        if not stock.news_items:
            return "No recent news for this ticker."

        pairs = list(zip(stock.news_items, stock.news_validations))[
            : self.prompt_headline_count
        ]

        lines = [
            f"- [{validation.verdict.value.upper()}] {item.headline}\n  {validation.note}"
            for item, validation in pairs
        ]
        return "\n".join(lines)
