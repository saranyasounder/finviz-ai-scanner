from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
from anthropic import APIStatusError

from analysis.claude_analyzer import ClaudeAnalyzer
from config.settings import ClaudeSettings
from models.fibonacci_levels import FibonacciLevels, TrendDirection
from models.news_item import NewsItem
from models.news_validation import NewsValidation, NewsVerdict
from models.stock_candidate import StockCandidate

PROMPTS_PATH = Path(__file__).resolve().parent.parent / "config" / "prompts.yaml"

_VALID_ANALYSIS_JSON = """{
  "action": "ENTER_NOW",
  "entry_zone": {"low": 9.5, "high": 10.5, "anchor_type": "FIBONACCI_SUPPORT", "anchor_price": 10.0},
  "stop_loss": 9.0,
  "target": {"price": 12.0, "risk_reward": "2.0R", "basis": "Nearest Fibonacci Resistance"},
  "risk_per_share": 1.0,
  "invalidation": "Break below 9.0 support.",
  "time_horizon": "Same-session intraday trade only. Exit before market close.",
  "confidence": {"score": 80, "grade": "HIGH"},
  "news_alignment": "NONE",
  "reasoning": "Strong momentum near support."
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
        max_tokens=650,
        temperature=0.15,
        request_timeout_seconds=5,
        min_score_to_analyze=min_score_to_analyze,
    )


def _analyzer(min_score_to_analyze: float = 0.0) -> ClaudeAnalyzer:
    return ClaudeAnalyzer(
        _claude_settings(min_score_to_analyze), PROMPTS_PATH, prompt_headline_count=2
    )


def _fake_response(content: str) -> MagicMock:
    response = MagicMock()
    response.content = [MagicMock(type="text", text=content)]
    return response


def _fake_low_credit_error() -> APIStatusError:
    http_response = httpx.Response(
        status_code=400, request=httpx.Request("POST", "https://example.invalid")
    )
    return APIStatusError(
        "Your credit balance is too low to access the Anthropic API.",
        response=http_response,
        body=None,
    )


def test_news_section_reports_no_news_for_this_ticker_when_empty():
    analyzer = _analyzer()
    stock = _stock()

    assert analyzer._build_news_section(stock) == "No recent news for this ticker."


def test_news_section_formats_verdict_and_headline():
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

    assert "[CORROBORATED] Beats estimates" in section
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


def test_market_state_section_reports_unavailable_when_no_fibonacci():
    stock = _stock()

    section = ClaudeAnalyzer._build_market_state_section(stock)

    assert "not available" in section.lower()
    assert "estimate the entry zone" in section.lower()


def test_market_state_section_includes_support_resistance_and_trend():
    stock = _stock(
        price=120.0,
        fibonacci=FibonacciLevels(
            swing_high=126.0,
            swing_low=95.0,
            levels={"0.5": 110.5},
            nearest_support=117.9,
            nearest_resistance=126.0,
            trend=TrendDirection.UPTREND,
        ),
    )

    section = ClaudeAnalyzer._build_market_state_section(stock)

    assert "117.90" in section
    assert "126.00" in section
    assert "uptrend" in section


def test_market_state_section_omits_resistance_line_when_absent():
    stock = _stock(
        price=120.0,
        fibonacci=FibonacciLevels(
            swing_high=126.0,
            swing_low=95.0,
            levels={"0.5": 110.5},
            nearest_support=117.9,
            nearest_resistance=None,
            trend=TrendDirection.UPTREND,
        ),
    )

    section = ClaudeAnalyzer._build_market_state_section(stock)

    assert "Nearest Fibonacci Resistance" not in section


def test_analyze_skips_candidates_below_min_score():
    analyzer = _analyzer(min_score_to_analyze=50)
    analyzer.client = MagicMock()
    analyzer.client.messages.create.return_value = _fake_response(_VALID_ANALYSIS_JSON)

    low = _stock(ticker="LOW", score=20.0)
    high = _stock(ticker="HIGH", score=80.0)

    result = analyzer.analyze([low, high])

    assert result[0].analysis is None
    assert result[1].analysis is not None
    assert result[1].analysis.action.value == "ENTER_NOW"
    analyzer.client.messages.create.assert_called_once()


def test_analyze_calls_everyone_when_min_score_is_zero():
    analyzer = _analyzer(min_score_to_analyze=0)
    analyzer.client = MagicMock()
    analyzer.client.messages.create.return_value = _fake_response(_VALID_ANALYSIS_JSON)

    stocks = [_stock(ticker="A", score=1.0), _stock(ticker="B", score=0.0)]

    result = analyzer.analyze(stocks)

    assert all(s.analysis is not None for s in result)
    assert analyzer.client.messages.create.call_count == 2


def test_analyze_stops_whole_batch_on_low_credit_balance_without_retrying_per_ticker():
    analyzer = _analyzer(min_score_to_analyze=0)
    analyzer.client = MagicMock()
    analyzer.client.messages.create.side_effect = _fake_low_credit_error()

    stocks = [_stock(ticker="A"), _stock(ticker="B"), _stock(ticker="C")]

    result = analyzer.analyze(stocks)

    assert all(s.analysis is None for s in result)
    # Only the first ticker was ever attempted - the rest were abandoned,
    # not retried, since a low credit balance is an account-level condition.
    analyzer.client.messages.create.assert_called_once()


def test_analyze_recovers_after_a_non_billing_failure_and_keeps_going():
    analyzer = _analyzer(min_score_to_analyze=0)
    analyzer.client = MagicMock()
    analyzer.client.messages.create.side_effect = [
        RuntimeError("transient network error"),
        _fake_response(_VALID_ANALYSIS_JSON),
    ]

    stocks = [_stock(ticker="A"), _stock(ticker="B")]

    result = analyzer.analyze(stocks)

    assert result[0].analysis is None
    assert result[1].analysis is not None
    assert analyzer.client.messages.create.call_count == 2


def test_analyze_parses_nested_schema_correctly():
    analyzer = _analyzer(min_score_to_analyze=0)
    analyzer.client = MagicMock()
    analyzer.client.messages.create.return_value = _fake_response(_VALID_ANALYSIS_JSON)

    result = analyzer.analyze([_stock()])
    analysis = result[0].analysis

    assert analysis.action.value == "ENTER_NOW"
    assert analysis.entry_zone.low == 9.5
    assert analysis.entry_zone.high == 10.5
    assert analysis.entry_zone.anchor_type.value == "FIBONACCI_SUPPORT"
    assert analysis.stop_loss == 9.0
    assert analysis.target.price == 12.0
    assert analysis.target.risk_reward == "2.0R"
    assert analysis.confidence.score == 80
    assert analysis.confidence.grade.value == "HIGH"
    assert analysis.news_alignment.value == "NONE"


def test_extract_text_skips_thinking_block_before_text_block():
    # Confirmed live: claude-sonnet-5 prepends a ThinkingBlock (extended
    # thinking) before the actual TextBlock - content[0] is not reliably text.
    response = MagicMock()
    response.content = [
        MagicMock(type="thinking", thinking="reasoning about the setup..."),
        MagicMock(type="text", text=_VALID_ANALYSIS_JSON),
    ]

    text = ClaudeAnalyzer._extract_text(response)

    assert text == _VALID_ANALYSIS_JSON


def test_extract_text_raises_when_no_text_block_present():
    response = MagicMock()
    response.content = [MagicMock(type="thinking", thinking="only thinking")]

    with pytest.raises(ValueError):
        ClaudeAnalyzer._extract_text(response)
