from datetime import date, timedelta

from utils.retention import TransientFileRetention


def _make_day_dir(tmp_path, day: date, file_sizes: list[int]) -> None:
    day_dir = tmp_path / day.isoformat()
    day_dir.mkdir(parents=True, exist_ok=True)
    for i, size in enumerate(file_sizes):
        (day_dir / f"finviz_{i}.csv").write_bytes(b"x" * size)


def test_keep_days_zero_deletes_everything_before_today(tmp_path):
    today = date(2026, 7, 27)
    yesterday = today - timedelta(days=1)

    _make_day_dir(tmp_path, yesterday, [100])
    _make_day_dir(tmp_path, today, [200])

    retention = TransientFileRetention(tmp_path, keep_days=0)
    removed = retention.cleanup(reference_date=today)

    assert removed == 1
    assert not (tmp_path / yesterday.isoformat()).exists()
    assert (tmp_path / today.isoformat()).exists()


def test_dry_run_does_not_delete_anything(tmp_path):
    today = date(2026, 7, 27)
    yesterday = today - timedelta(days=1)

    _make_day_dir(tmp_path, yesterday, [100])

    retention = TransientFileRetention(tmp_path, keep_days=0)
    would_remove = retention.cleanup(dry_run=True, reference_date=today)

    assert would_remove == 1
    assert (tmp_path / yesterday.isoformat()).exists()
    assert list((tmp_path / yesterday.isoformat()).iterdir())


def test_keep_days_n_retains_recent_folders(tmp_path):
    today = date(2026, 7, 27)
    two_days_ago = today - timedelta(days=2)
    five_days_ago = today - timedelta(days=5)

    _make_day_dir(tmp_path, two_days_ago, [50])
    _make_day_dir(tmp_path, five_days_ago, [50])

    retention = TransientFileRetention(tmp_path, keep_days=3)
    retention.cleanup(reference_date=today)

    assert (tmp_path / two_days_ago.isoformat()).exists()
    assert not (tmp_path / five_days_ago.isoformat()).exists()


def test_freed_bytes_are_accurate(tmp_path, capsys):
    today = date(2026, 7, 27)
    yesterday = today - timedelta(days=1)

    _make_day_dir(tmp_path, yesterday, [1024, 2048])

    retention = TransientFileRetention(tmp_path, keep_days=0)
    removed = retention.cleanup(reference_date=today)

    assert removed == 2


def test_nonexistent_downloads_dir_returns_zero(tmp_path):
    retention = TransientFileRetention(tmp_path / "does_not_exist", keep_days=0)

    assert retention.cleanup() == 0


def test_non_date_named_entries_are_ignored(tmp_path):
    (tmp_path / "not-a-date").mkdir()
    (tmp_path / "stray_file.txt").write_text("hello")

    retention = TransientFileRetention(tmp_path, keep_days=0)
    removed = retention.cleanup(reference_date=date(2026, 7, 27))

    assert removed == 0
    assert (tmp_path / "not-a-date").exists()
    assert (tmp_path / "stray_file.txt").exists()
