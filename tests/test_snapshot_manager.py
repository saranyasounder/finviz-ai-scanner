from datetime import datetime

from models.stock_candidate import StockCandidate
from storage.snapshot_manager import SnapshotManager


def _stock(ticker="AAA", score=10.0) -> StockCandidate:
    return StockCandidate(
        ticker=ticker,
        company=ticker,
        sector="Technology",
        industry="Software",
        country="USA",
        price=10.0,
        change=0.0,
        volume=1_000_000,
        score=score,
    )


def test_save_and_load_latest(tmp_path):
    manager = SnapshotManager(tmp_path, retention_days=30)
    timestamp = datetime(2026, 7, 25, 6, 0)

    manager.save([_stock()], timestamp=timestamp)

    loaded = manager.load_latest()

    assert loaded is not None
    assert loaded[0].ticker == "AAA"
    assert (tmp_path / "2026-07-25" / "06-00.json").exists()


def test_load_previous_returns_second_to_last(tmp_path):
    manager = SnapshotManager(tmp_path, retention_days=30)

    manager.save([_stock("AAA")], timestamp=datetime(2026, 7, 25, 6, 0))
    manager.save([_stock("BBB")], timestamp=datetime(2026, 7, 25, 6, 1))

    previous = manager.load_previous()
    latest = manager.load_latest()

    assert previous[0].ticker == "AAA"
    assert latest[0].ticker == "BBB"


def test_load_latest_returns_none_when_empty(tmp_path):
    manager = SnapshotManager(tmp_path, retention_days=30)

    assert manager.load_latest() is None
    assert manager.load_previous() is None


def test_cleanup_old_removes_expired_snapshots(tmp_path):
    manager = SnapshotManager(tmp_path, retention_days=1)

    manager.save([_stock()], timestamp=datetime(2020, 1, 1, 6, 0))
    removed = manager.cleanup_old(reference_time=datetime(2026, 7, 25, 6, 0))

    assert removed == 1
    assert manager.load_latest() is None
