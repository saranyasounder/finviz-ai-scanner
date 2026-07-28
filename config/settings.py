"""Central configuration: merges config/settings.yaml with .env secrets into one Settings object."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@dataclass(frozen=True)
class BrowserSettings:
    profile_dir: Path
    headless: bool
    download_timeout_ms: int


@dataclass(frozen=True)
class MarketHours:
    timezone: str
    start_hour: int
    start_minute: int
    end_hour: int
    end_minute: int
    days: str


@dataclass(frozen=True)
class SnapshotSettings:
    directory: Path
    retention_days: int
    top_n: int


@dataclass(frozen=True)
class ChangeDetectionThresholds:
    score_delta: float
    relative_volume_delta: float
    gap_delta_pct: float
    price_delta_pct: float


@dataclass(frozen=True)
class ClaudeSettings:
    api_key: str
    model: str
    max_tokens: int
    base_url: str
    site_url: str
    site_name: str
    request_timeout_seconds: float


@dataclass(frozen=True)
class EnrichmentSettings:
    fibonacci_lookback_days: int
    news_max_headlines: int
    prompt_headline_count: int
    news_fetch_delay_seconds: float


@dataclass(frozen=True)
class EmailSettings:
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    from_addr: str
    to_addrs: list[str]
    subject_prefix: str
    smtp_timeout_seconds: float


@dataclass(frozen=True)
class LoggingSettings:
    directory: Path
    rotation: str
    retention: str
    level: str


@dataclass(frozen=True)
class RetentionSettings:
    downloads_keep_days: int


@dataclass(frozen=True)
class OutcomeTrackingSettings:
    checkpoint_minutes: list[int]
    conviction_bucket_high: float
    conviction_bucket_medium: float


@dataclass(frozen=True)
class Settings:
    base_dir: Path
    downloads_dir: Path
    finviz_screener_url: str
    browser: BrowserSettings
    market_hours: MarketHours
    snapshots: SnapshotSettings
    change_detection: ChangeDetectionThresholds
    claude: ClaudeSettings
    enrichment: EnrichmentSettings
    email: EmailSettings
    logging: LoggingSettings
    retention: RetentionSettings
    outcome_tracking: OutcomeTrackingSettings
    scoring_config_path: Path
    prompts_config_path: Path
    market_holidays_config_path: Path
    ranking_config_path: Path
    outcomes_db_path: Path


def load_settings(config_dir: Path | None = None) -> Settings:
    """Load settings.yaml plus .env secrets into a single immutable Settings object."""

    config_dir = config_dir or (BASE_DIR / "config")
    raw = _load_yaml(config_dir / "settings.yaml")

    screener_url = os.getenv("FINVIZ_SCREENER_URL")
    if not screener_url:
        raise RuntimeError("FINVIZ_SCREENER_URL is not set in the environment (.env).")

    to_addrs_raw = os.getenv("EMAIL_TO", "")
    to_addrs = [addr.strip() for addr in to_addrs_raw.split(",") if addr.strip()]

    return Settings(
        base_dir=BASE_DIR,
        downloads_dir=BASE_DIR / "downloads",
        finviz_screener_url=screener_url,
        browser=BrowserSettings(
            profile_dir=BASE_DIR / raw["browser"]["profile_dir"],
            headless=raw["browser"]["headless"],
            download_timeout_ms=raw["browser"]["download_timeout_ms"],
        ),
        market_hours=MarketHours(**raw["market_hours"]),
        snapshots=SnapshotSettings(
            directory=BASE_DIR / raw["snapshots"]["directory"],
            retention_days=raw["snapshots"]["retention_days"],
            top_n=raw["snapshots"]["top_n"],
        ),
        change_detection=ChangeDetectionThresholds(**raw["change_detection"]),
        claude=ClaudeSettings(
            api_key=os.getenv("OPENROUTER_API_KEY", ""),
            model=raw["claude"]["model"],
            max_tokens=raw["claude"]["max_tokens"],
            base_url=raw["claude"]["base_url"],
            site_url=raw["claude"]["site_url"],
            site_name=raw["claude"]["site_name"],
            request_timeout_seconds=raw["claude"]["request_timeout_seconds"],
        ),
        enrichment=EnrichmentSettings(**raw["enrichment"]),
        email=EmailSettings(
            smtp_host=os.getenv("SMTP_HOST", ""),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_username=os.getenv("SMTP_USERNAME", ""),
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
            from_addr=os.getenv("EMAIL_FROM", ""),
            to_addrs=to_addrs,
            subject_prefix=raw["email"]["subject_prefix"],
            smtp_timeout_seconds=raw["email"]["smtp_timeout_seconds"],
        ),
        logging=LoggingSettings(
            directory=BASE_DIR / raw["logging"]["directory"],
            rotation=raw["logging"]["rotation"],
            retention=raw["logging"]["retention"],
            level=raw["logging"]["level"],
        ),
        retention=RetentionSettings(**raw["retention"]),
        outcome_tracking=OutcomeTrackingSettings(**raw["outcome_tracking"]),
        scoring_config_path=config_dir / "scoring.yaml",
        prompts_config_path=config_dir / "prompts.yaml",
        market_holidays_config_path=config_dir / "market_holidays.yaml",
        ranking_config_path=config_dir / "ranking.yaml",
        outcomes_db_path=BASE_DIR / "data" / "outcomes.db",
    )
