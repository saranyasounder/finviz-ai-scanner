import pytest

from config.settings import load_settings

_SETTINGS_YAML = """
browser:
  profile_dir: chrome_profile
  headless: false
  download_timeout_ms: 15000

market_hours:
  timezone: America/New_York
  start_hour: 9
  start_minute: 30
  end_hour: 16
  end_minute: 0
  days: mon-fri

snapshots:
  directory: data/snapshots
  retention_days: 30
  top_n: 10

change_detection:
  score_delta: 5.0
  relative_volume_delta: 0.5
  gap_delta_pct: 1.0
  price_delta_pct: 1.0

claude:
  model: anthropic/claude-sonnet-5
  max_tokens: 1024
  base_url: https://openrouter.ai/api/v1
  site_url: https://example.invalid
  site_name: Test
  request_timeout_seconds: 30

enrichment:
  fibonacci_lookback_days: 90
  news_max_headlines: 5
  prompt_headline_count: 3
  news_fetch_delay_seconds: 1.5

email:
  subject_prefix: "[Test]"
  smtp_timeout_seconds: 15

logging:
  directory: logs
  rotation: "00:00"
  retention: "14 days"
  level: INFO

retention:
  downloads_keep_days: 0

outcome_tracking:
  checkpoint_minutes: [30, 60, 240, 1440]
  conviction_bucket_high: 70
  conviction_bucket_medium: 40
"""


def _write_settings_yaml(tmp_path) -> None:
    (tmp_path / "settings.yaml").write_text(_SETTINGS_YAML, encoding="utf-8")


def test_missing_screener_url_raises(tmp_path, monkeypatch):
    _write_settings_yaml(tmp_path)
    monkeypatch.delenv("FINVIZ_SCREENER_URL", raising=False)

    with pytest.raises(RuntimeError):
        load_settings(config_dir=tmp_path)


def test_happy_path_loads_settings(tmp_path, monkeypatch):
    _write_settings_yaml(tmp_path)
    monkeypatch.setenv("FINVIZ_SCREENER_URL", "https://example.invalid/screener")
    monkeypatch.setenv("EMAIL_TO", "a@example.com, b@example.com")

    settings = load_settings(config_dir=tmp_path)

    assert settings.finviz_screener_url == "https://example.invalid/screener"
    assert settings.market_hours.timezone == "America/New_York"
    assert settings.market_hours.start_minute == 30
    assert settings.email.to_addrs == ["a@example.com", "b@example.com"]
    assert settings.enrichment.news_fetch_delay_seconds == 1.5
    assert settings.scoring_config_path == tmp_path / "scoring.yaml"


def test_email_to_defaults_to_empty_list_when_unset(tmp_path, monkeypatch):
    _write_settings_yaml(tmp_path)
    monkeypatch.setenv("FINVIZ_SCREENER_URL", "https://example.invalid/screener")
    monkeypatch.delenv("EMAIL_TO", raising=False)

    settings = load_settings(config_dir=tmp_path)

    assert settings.email.to_addrs == []
