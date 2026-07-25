from analysis.change_detector import ChangeDetector
from config.settings import ChangeDetectionThresholds
from models.change_event import ChangeType
from models.stock_candidate import StockCandidate


def _stock(ticker, score, price=10.0, relative_volume=2.0, gap=1.0) -> StockCandidate:
    return StockCandidate(
        ticker=ticker,
        company=ticker,
        sector="Technology",
        industry="Software",
        country="USA",
        price=price,
        change=0.0,
        volume=1_000_000,
        relative_volume=relative_volume,
        gap=gap,
        score=score,
    )


def _thresholds() -> ChangeDetectionThresholds:
    return ChangeDetectionThresholds(
        score_delta=5.0,
        relative_volume_delta=0.5,
        gap_delta_pct=1.0,
        price_delta_pct=1.0,
    )


def test_new_ticker_generates_new_event():
    detector = ChangeDetector(_thresholds(), top_n=10)
    current = [_stock("AAA", score=50)]

    events = detector.detect(current, previous=None)

    assert any(e.change_type == ChangeType.NEW for e in events)


def test_score_change_past_threshold_detected():
    detector = ChangeDetector(_thresholds(), top_n=10)
    previous = [_stock("AAA", score=50)]
    current = [_stock("AAA", score=60)]

    events = detector.detect(current, previous)

    assert any(e.change_type == ChangeType.SCORE_CHANGE for e in events)


def test_small_score_change_ignored():
    detector = ChangeDetector(_thresholds(), top_n=10)
    previous = [_stock("AAA", score=50)]
    current = [_stock("AAA", score=52)]

    events = detector.detect(current, previous)

    assert events == []


def test_top_n_entry_and_exit_detected():
    detector = ChangeDetector(_thresholds(), top_n=1)

    previous = [_stock("AAA", score=90), _stock("BBB", score=10)]
    current = [_stock("BBB", score=95), _stock("AAA", score=90)]

    events = detector.detect(current, previous)

    entered = {e.ticker for e in events if e.change_type == ChangeType.ENTERED_TOP_N}
    left = {e.ticker for e in events if e.change_type == ChangeType.LEFT_TOP_N}

    assert entered == {"BBB"}
    assert left == {"AAA"}
