from pathlib import Path

from analysis.candidate_selector import CandidateSelector
from models.stock_candidate import StockCandidate


def _stock(ticker: str, volume: int, score: float = 50.0) -> StockCandidate:
    return StockCandidate(
        ticker=ticker,
        company=f"{ticker} Corp",
        sector="Technology",
        industry="Software",
        country="USA",
        price=10.0,
        change=1.0,
        volume=volume,
        relative_volume=1.0,
        score=score,
    )


def _selector(tmp_path, volume_top_n: int = 10) -> CandidateSelector:
    config_path = tmp_path / "analysis.yaml"
    config_path.write_text(f"volume_top_n: {volume_top_n}\n", encoding="utf-8")
    return CandidateSelector(config_path)


def test_selects_top_n_by_raw_volume_descending(tmp_path):
    selector = _selector(tmp_path, volume_top_n=2)
    stocks = [
        _stock("LOW", volume=1_000),
        _stock("HIGH", volume=5_000_000),
        _stock("MID", volume=500_000),
    ]

    selected = selector.select(stocks)

    assert [s.ticker for s in selected] == ["HIGH", "MID"]


def test_ignores_relative_volume_uses_raw_volume(tmp_path):
    selector = _selector(tmp_path, volume_top_n=1)
    # THIN has a huge relative_volume (unusual for itself) but tiny absolute
    # liquidity; LIQUID has modest relative_volume but massive raw volume.
    # The selector must pick LIQUID - liquidity/fillability, not unusualness.
    thin_but_spiking = _stock("THIN", volume=20_000)
    thin_but_spiking.relative_volume = 15.0
    liquid_but_calm = _stock("LIQUID", volume=10_000_000)
    liquid_but_calm.relative_volume = 1.1

    selected = selector.select([thin_but_spiking, liquid_but_calm])

    assert [s.ticker for s in selected] == ["LIQUID"]


def test_selects_fewer_than_n_when_fewer_candidates_exist(tmp_path):
    selector = _selector(tmp_path, volume_top_n=10)
    stocks = [_stock("A", volume=100), _stock("B", volume=200)]

    selected = selector.select(stocks)

    assert len(selected) == 2


def test_empty_input_returns_empty_list(tmp_path):
    selector = _selector(tmp_path, volume_top_n=10)

    assert selector.select([]) == []


def test_volume_top_n_loaded_from_config(tmp_path):
    selector = _selector(tmp_path, volume_top_n=3)

    assert selector.volume_top_n == 3
