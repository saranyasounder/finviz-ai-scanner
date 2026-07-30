from pathlib import Path
from unittest.mock import MagicMock

import httpx
from openai import APIStatusError

from analysis.claude_analyzer import ClaudeAnalyzer
from config.settings import ClaudeSettings
from models.fibonacci_levels import FibonacciLevels, TrendDirection
from models.news_item import NewsItem
from models.news_validation import NewsValidation, NewsVerdict
from models.stock_candidate import StockCandidate

PROMPTS_PATH = Path(__file__).resolve().parent.parent / "config" / "prompts.yaml"

_VALID_ANALYSIS_JSON = """{
  "reasoning": "Strong momentum.",
  "risk": "Overbought.",
  "entry": "10",
  "stop_loss": "9",
  "profit_target": "12",
  "confidence": "High",
  "trade_quality": "A"
}"""


def _stock(**overrides) -> StockCandidate:
    base = dict(
        ticker="AAA",
        company="AAA Corp",
        sector="Technology",
        industry="Software",
        country="USA",
        price=10.0,
        change=1.0,
        volume=1_000_000,
        score=80.0,
    )
    base.update(overrides)
    return StockCandidate(**base)


def _claude_settings(min_score_to_analyze: float = 0.0) -> ClaudeSettings:
    return ClaudeSettings(
        api_key="test-key",
        model="test-model",
        max_tokens=100,
        base_url="https://example.invalid",
        site_url="https://example.invalid",
        site_name="Test",
        request_timeout_seconds=5,
        min_score_to_analyze=min_score_to_analyze,
    )


def _analyzer(min_score_to_analyze: float = 0.0) -> ClaudeAnalyzer:
    return ClaudeAnalyzer(
        _claude_settings(min_score_to_analyze), PROMPTS_PATH, prompt_headline_count=2
    )


def _fake_response(content: str) -> MagicMock:
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=content))]
    return response


def _fake_402_error() -> APIStatusError:
    http_response = httpx.Response(
        status_code=402, request=httpx.Request("POST", "https://example.invalid")
    )
    return APIStatusError("insufficient credits", response=http_response, body=None)


def test_news_section_reports_no_news_when_empty():
    analyzer = _analyzer()
    stock = _stock()

    assert analyzer._build_news_section(stock) == "No recent news available."


def test_news_section_pairs_headlines_with_verdicts():
    analyzer = _analyzer()
    stock = _stock(
        news_items=[NewsItem(headline="Beats estimates", source="Reuters")],
        news_validations=[
            NewsValidation(
                headline="Beats estimates",
                verdict=NewsVerdict.CORROBORATED,
                note="Matches price up.",
            )
        ],
    )

    section = analyzer._build_news_section(stock)

    assert "Beats estimates" in section
    assert "Reuters" in section
    assert "CORROBORATED" in section
    assert "Matches price up." in section


def test_news_section_truncates_to_prompt_headline_count():
    analyzer = _analyzer()
    items = [NewsItem(headline=f"Headline {i}") for i in range(5)]
    validations = [
        NewsValidation(
            headline=f"Headline {i}", verdict=NewsVerdict.INCONCLUSIVE, note="n/a"
        )
        for i in range(5)
    ]
    stock = _stock(news_items=items, news_validations=validations)

    section = analyzer._build_news_section(stock)

    assert section.count("Headline") == 2


def test_fibonacci_section_reports_no_data_when_absent():
    stock = _stock()

    assert (
        ClaudeAnalyzer._build_fibonacci_section(stock) == "No Fibonacci data available."
    )


def test_fibonacci_section_includes_trend_and_levels():
    stock = _stock(
        fibonacci=FibonacciLevels(
            swing_high=126.0,
            swing_low=95.0,
            levels={"0.5": 110.5},
            nearest_support=117.9,
            nearest_resistance=126.0,
            trend=TrendDirection.UPTREND,
        )
    )

    section = ClaudeAnalyzer._build_fibonacci_section(stock)

    assert "uptrend" in section
    assert "126.00" in section
    assert "95.00" in section
    assert "117.9" in section


def test_analyze_skips_candidates_below_min_score():
    analyzer = _analyzer(min_score_to_analyze=50)
    analyzer.client = MagicMock()
    analyzer.client.chat.completions.create.return_value = _fake_response(
        _VALID_ANALYSIS_JSON
    )

    low = _stock(ticker="LOW", score=20.0)
    high = _stock(ticker="HIGH", score=80.0)

    result = analyzer.analyze([low, high], {})

    assert result[0].analysis is None
    assert result[1].analysis is not None
    analyzer.client.chat.completions.create.assert_called_once()


def test_analyze_calls_everyone_when_min_score_is_zero():
    analyzer = _analyzer(min_score_to_analyze=0)
    analyzer.client = MagicMock()
    analyzer.client.chat.completions.create.return_value = _fake_response(
        _VALID_ANALYSIS_JSON
    )

    stocks = [_stock(ticker="A", score=1.0), _stock(ticker="B", score=0.0)]

    result = analyzer.analyze(stocks, {})

    assert all(s.analysis is not None for s in result)
    assert analyzer.client.chat.completions.create.call_count == 2


def test_analyze_stops_whole_batch_on_402_without_retrying_per_ticker():
    analyzer = _analyzer(min_score_to_analyze=0)
    analyzer.client = MagicMock()
    analyzer.client.chat.completions.create.side_effect = _fake_402_error()

    stocks = [_stock(ticker="A"), _stock(ticker="B"), _stock(ticker="C")]

    result = analyzer.analyze(stocks, {})

    assert all(s.analysis is None for s in result)
    # Only the first ticker was ever attempted - the rest were abandoned,
    # not retried, since a 402 is an account-level condition.
    analyzer.client.chat.completions.create.assert_called_once()


def test_analyze_recovers_after_a_non_402_failure_and_keeps_going():
    analyzer = _analyzer(min_score_to_analyze=0)
    analyzer.client = MagicMock()
    analyzer.client.chat.completions.create.side_effect = [
        RuntimeError("transient network error"),
        _fake_response(_VALID_ANALYSIS_JSON),
    ]

    stocks = [_stock(ticker="A"), _stock(ticker="B")]

    result = analyzer.analyze(stocks, {})

    assert result[0].analysis is None
    assert result[1].analysis is not None
    assert analyzer.client.chat.completions.create.call_count == 2
