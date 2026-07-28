from datetime import datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

from app import _maybe_run_end_of_day_cleanup


def _settings(tmp_path):
    settings = MagicMock()
    settings.base_dir = tmp_path
    settings.downloads_dir = tmp_path / "downloads"
    settings.snapshots.directory = tmp_path / "data" / "snapshots"
    settings.retention.downloads_keep_days = 0
    return settings


def _guard(is_open: bool):
    guard = MagicMock()
    guard.timezone = ZoneInfo("America/New_York")
    guard.is_market_open.return_value = is_open
    return guard


def test_skips_when_market_still_open(tmp_path):
    settings = _settings(tmp_path)
    guard = _guard(is_open=True)

    _maybe_run_end_of_day_cleanup(settings, guard)

    assert not (tmp_path / "data" / ".retention_marker").exists()


def test_skips_when_no_snapshot_produced_today(tmp_path):
    settings = _settings(tmp_path)
    guard = _guard(is_open=False)

    _maybe_run_end_of_day_cleanup(settings, guard)

    assert not (tmp_path / "data" / ".retention_marker").exists()


def test_runs_cleanup_and_writes_marker_once_today_snapshot_exists(tmp_path):
    settings = _settings(tmp_path)
    guard = _guard(is_open=False)
    today = datetime.now(guard.timezone).date()

    snapshot_dir = settings.snapshots.directory / today.isoformat()
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "16-00.json").write_text("{}")

    old_download_dir = settings.downloads_dir / "2020-01-01"
    old_download_dir.mkdir(parents=True)
    (old_download_dir / "finviz_10-00-00.csv").write_text("data")

    _maybe_run_end_of_day_cleanup(settings, guard)

    marker = tmp_path / "data" / ".retention_marker"
    assert marker.exists()
    assert marker.read_text().strip() == today.isoformat()
    assert not old_download_dir.exists()


def test_does_not_rerun_once_already_marked_today(tmp_path):
    settings = _settings(tmp_path)
    guard = _guard(is_open=False)
    today = datetime.now(guard.timezone).date()

    snapshot_dir = settings.snapshots.directory / today.isoformat()
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "16-00.json").write_text("{}")

    marker = tmp_path / "data" / ".retention_marker"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(today.isoformat())

    old_download_dir = settings.downloads_dir / "2020-01-01"
    old_download_dir.mkdir(parents=True)
    (old_download_dir / "finviz.csv").write_text("data")

    _maybe_run_end_of_day_cleanup(settings, guard)

    assert old_download_dir.exists()
