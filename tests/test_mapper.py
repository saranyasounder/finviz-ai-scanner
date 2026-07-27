import pandas as pd

from finviz.mapper import FinvizMapper


def _row(**overrides) -> pd.Series:
    base = {
        "Ticker": "AAPL",
        "Company": "Apple Inc",
        "Sector": "Technology",
        "Industry": "Consumer Electronics",
        "Country": "USA",
        "Market Cap": "3.2B",
        "Price": "190.50",
        "Change": "2.5%",
        "Volume": "50M",
        "Average Volume": "45M",
        "Relative Volume": "1.8",
        "Average True Range": "3.2",
        "Float %": "60.5%",
        "Relative Strength Index (14)": "65.2",
        "Gap": "1.2%",
        "Performance (4 Hours)": "0.8%",
        "20-Day Simple Moving Average": "5.1%",
        "50-Day Simple Moving Average": "8.3%",
        "Beta": "1.25",
        "Short Float": "0.9%",
        "Institutional Ownership": "62.1%",
    }
    base.update(overrides)
    return pd.Series(base)


def test_maps_identity_fields_directly():
    stock = FinvizMapper.map(_row())

    assert stock.ticker == "AAPL"
    assert stock.company == "Apple Inc"
    assert stock.sector == "Technology"
    assert stock.industry == "Consumer Electronics"
    assert stock.country == "USA"


def test_maps_and_normalizes_numeric_fields():
    stock = FinvizMapper.map(_row())

    assert stock.price == 190.50
    assert stock.change == 2.5
    assert stock.volume == 50_000_000
    assert stock.average_volume == 45_000_000
    assert stock.relative_volume == 1.8
    assert stock.atr == 3.2
    assert stock.rsi == 65.2
    assert stock.gap == 1.2
    assert stock.beta == 1.25
    assert stock.short_float == 0.9
    assert stock.institutional_ownership == 62.1


def test_handles_missing_optional_values():
    stock = FinvizMapper.map(_row(**{"Market Cap": "-", "Beta": "-"}))

    assert stock.market_cap is None
    assert stock.beta is None


def test_new_stock_starts_unscored_and_unenriched():
    stock = FinvizMapper.map(_row())

    assert stock.score == 0.0
    assert stock.score_breakdown == {}
    assert stock.analysis is None
    assert stock.news_items == []
    assert stock.fibonacci is None
