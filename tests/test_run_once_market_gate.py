"""Locks in what was previously only verified by a manual smoke test: run_once()
must not build/run the TradingEngine at all when the market is closed."""

from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import app


def test_run_once_does_not_build_or_run_engine_when_market_closed(tmp_path):
    fake_settings = MagicMock()
    fake_settings.base_dir = tmp_path
    fake_settings.snapshots.directory = tmp_path / "data" / "snapshots"

    with patch("app.load_settings", return_value=fake_settings), patch(
        "app.configure_logging"
    ), patch("app.MarketHoursGuard") as mock_guard_cls, patch(
        "app.TradingEngine"
    ) as mock_engine_cls:
        mock_guard_cls.return_value.is_market_open.return_value = False
        mock_guard_cls.return_value.timezone = ZoneInfo("America/New_York")

        app.run_once()

        mock_engine_cls.from_settings.assert_not_called()


def test_run_once_builds_and_runs_engine_when_market_open(tmp_path):
    fake_settings = MagicMock()
    fake_settings.base_dir = tmp_path
    fake_settings.snapshots.directory = tmp_path / "data" / "snapshots"

    with patch("app.load_settings", return_value=fake_settings), patch(
        "app.configure_logging"
    ), patch("app.MarketHoursGuard") as mock_guard_cls, patch(
        "app.TradingEngine"
    ) as mock_engine_cls:
        mock_guard_cls.return_value.is_market_open.return_value = True
        mock_guard_cls.return_value.timezone = ZoneInfo("America/New_York")
        mock_engine = MagicMock()
        mock_engine_cls.from_settings.return_value = mock_engine

        app.run_once()

        mock_engine_cls.from_settings.assert_called_once_with(fake_settings)
        mock_engine.run.assert_called_once()
