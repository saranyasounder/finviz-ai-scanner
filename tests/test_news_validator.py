from analysis.news_validator import NewsValidator
from models.news_item import NewsItem
from models.news_validation import NewsVerdict
from models.stock_candidate import StockCandidate


def _stock(change: float, headlines: list[str]) -> StockCandidate:
    return StockCandidate(
        ticker="AAA",
        company="AAA Corp",
        sector="Technology",
        industry="Software",
        country="USA",
        price=10.0,
        change=change,
        volume=1_000_000,
        news_items=[NewsItem(headline=h) for h in headlines],
    )


def test_bullish_headline_matches_price_up_is_corroborated():
    validator = NewsValidator()
    stock = _stock(change=5.0, headlines=["Company Beats Earnings Estimates"])

    results = validator.validate(stock)

    assert results[0].verdict == NewsVerdict.CORROBORATED


def test_bullish_headline_with_price_down_is_conflicting():
    validator = NewsValidator()
    stock = _stock(change=-5.0, headlines=["Company Beats Earnings Estimates"])

    results = validator.validate(stock)

    assert results[0].verdict == NewsVerdict.CONFLICTING


def test_bearish_headline_matches_price_down_is_corroborated():
    validator = NewsValidator()
    stock = _stock(change=-4.0, headlines=["Analyst Downgrade Sends Shares Lower"])

    results = validator.validate(stock)

    assert results[0].verdict == NewsVerdict.CORROBORATED


def test_bearish_headline_with_price_up_is_conflicting():
    validator = NewsValidator()
    stock = _stock(change=4.0, headlines=["Company Issues Recall Warning"])

    results = validator.validate(stock)

    assert results[0].verdict == NewsVerdict.CONFLICTING


def test_no_keywords_is_inconclusive():
    validator = NewsValidator()
    stock = _stock(
        change=3.0, headlines=["Company Announces Annual Shareholder Meeting Date"]
    )

    results = validator.validate(stock)

    assert results[0].verdict == NewsVerdict.INCONCLUSIVE


def test_negligible_price_move_is_inconclusive_despite_keywords():
    validator = NewsValidator()
    stock = _stock(change=0.1, headlines=["Company Beats Earnings Estimates"])

    results = validator.validate(stock)

    assert results[0].verdict == NewsVerdict.INCONCLUSIVE


def test_results_preserve_order_and_length():
    validator = NewsValidator()
    stock = _stock(
        change=5.0,
        headlines=["Beats estimates", "Unrelated headline", "Downgrade issued"],
    )

    results = validator.validate(stock)

    assert len(results) == 3
    assert [r.headline for r in results] == [item.headline for item in stock.news_items]
