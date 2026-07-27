from pathlib import Path

from analysis.claude_analyzer import ClaudeAnalyzer
from config.settings import ClaudeSettings
from models.fibonacci_levels import FibonacciLevels, TrendDirection
from models.news_item import NewsItem
from models.news_validation import NewsValidation, NewsVerdict
from models.stock_candidate import StockCandidate

PROMPTS_PATH = Path(__file__).resolve().parent.parent / "config" / "prompts.yaml"


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
    )
    base.update(overrides)
    return StockCandidate(**base)


def _claude_settings() -> ClaudeSettings:
    return ClaudeSettings(
        api_key="test-key",
        model="test-model",
        max_tokens=100,
        base_url="https://example.invalid",
        site_url="https://example.invalid",
        site_name="Test",
        request_timeout_seconds=5,
    )


def _analyzer() -> ClaudeAnalyzer:
    return ClaudeAnalyzer(_claude_settings(), PROMPTS_PATH, prompt_headline_count=2)


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
        NewsValidation(headline=f"Headline {i}", verdict=NewsVerdict.INCONCLUSIVE, note="n/a")
        for i in range(5)
    ]
    stock = _stock(news_items=items, news_validations=validations)

    section = analyzer._build_news_section(stock)

    assert section.count("Headline") == 2


def test_fibonacci_section_reports_no_data_when_absent():
    stock = _stock()

    assert ClaudeAnalyzer._build_fibonacci_section(stock) == "No Fibonacci data available."


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
