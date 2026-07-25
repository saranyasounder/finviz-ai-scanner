from finviz.normalizer import FinvizNormalizer


def test_to_float_handles_suffixes():
    assert FinvizNormalizer.to_float("1.5B") == 1_500_000_000
    assert FinvizNormalizer.to_float("250M") == 250_000_000
    assert FinvizNormalizer.to_float("10K") == 10_000


def test_to_float_handles_percent():
    assert FinvizNormalizer.to_float("12.5%") == 12.5


def test_to_float_handles_missing_values():
    assert FinvizNormalizer.to_float("-") is None
    assert FinvizNormalizer.to_float("") is None
    assert FinvizNormalizer.to_float(float("nan")) is None


def test_to_int_truncates():
    assert FinvizNormalizer.to_int("1.9M") == 1_900_000
