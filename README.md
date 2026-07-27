# Finviz AI Trading Intelligence Platform

An automated momentum-stock scanner: logs into Finviz Elite, downloads the
saved screener, scores candidates against a configurable rule engine, detects
only meaningful changes since the last scan, enriches the changed stocks with
recent news corroboration and Fibonacci retracement levels, sends just those
stocks to Claude (via OpenRouter) for a trade write-up, and emails an HTML
report - only when there's something worth reporting.

Runs unattended on a 15-minute cycle during NYSE regular hours, holiday-aware,
DST-safe. Nothing in the scheduling loop is an agent/LLM decision - Claude is
only ever called *inside* a run, to analyze already-selected stocks.

## Architecture

```
runner.py (or cron) --calls--> app.py:run_once()
                                     |
                              MarketHoursGuard  -- closed? no-op, return
                                     |
                              TradingEngine.run()
                                     |
                          FinvizCollector.collect()      (browser -> screener -> download -> load -> parse)
                                     |
                          MomentumScorer.score_all()      (config/scoring.yaml rules)
                                     |
                          SnapshotManager.load_latest()   (data/snapshots/YYYY-MM-DD/HH-MM.json)
                                     |
                          ChangeDetector.detect()          --> no changes? save snapshot, stop (no email)
                                     |
                          EnrichmentService.enrich()       (news + Fibonacci, changed stocks only)
                                     |
                          ClaudeAnalyzer.analyze()         (OpenRouter, changed stocks only)
                                     |
                          ReportGenerator.generate()        (Jinja2 HTML)
                                     |
                          EmailService.send()
                                     |
                          SnapshotManager.save() + cleanup_old()
```

Every box above is one class with one responsibility; `TradingEngine` is the
only place that wires them together and owns the business logic. `runner.py`
and `app.py` never decide *what* happens, only *when*.

## Project layout

```
app.py                    CLI entrypoint: run_once() (market-hours gated pipeline run)
runner.py                 Persistent-process scheduler: ticks run_once() every 15 minutes
engine.py                 TradingEngine - orchestrates one full scan cycle

browser/                  Persistent Playwright Chromium session (Finviz Elite login)
finviz/                   Screener navigation, CSV download/load/parse, per-ticker news scraping
market_data/               Price history independent of Finviz (yfinance)
analysis/                 Scoring, change detection, enrichment, Claude analysis
models/                   Pydantic models (StockCandidate, ChangeEvent, NewsItem, FibonacciLevels, ...)
storage/                  Snapshot persistence + retention cleanup
reports/                  Jinja2 HTML report generation
notifications/            Email delivery (not `email/` - would shadow the stdlib module)
config/                   settings.yaml, scoring.yaml, prompts.yaml, market_holidays.yaml + loader
utils/                    Shared exceptions, logging setup, market-hours calendar, timing helper
tests/                    Unit tests - no live network/browser in any of them
```

## Setup

```bash
python -m venv venv
venv\Scripts\pip install -r requirements-dev.txt   # includes requirements.txt
```

Create `.env` (git-ignored) with:

```
FINVIZ_SCREENER_URL=<your saved Finviz Elite screener URL>
OPENROUTER_API_KEY=<your OpenRouter key, sk-or-v1-...>
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=<your email>
SMTP_PASSWORD=<an app password, not your account password>
EMAIL_FROM=<your email>
EMAIL_TO=<comma-separated recipient list>
```

First-time login (creates the persistent `chrome_profile/` session):

```bash
venv\Scripts\python -m browser.manual_login
```

## Running it

```bash
venv\Scripts\python app.py --once     # single cycle, no-ops if the market is closed
venv\Scripts\python runner.py         # persistent process, ticks every 15 minutes
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for the two supported unattended deployment
shapes (systemd running `runner.py`, or system cron running `app.py --once`)
and the tradeoff between them.

## Configuration

Nothing is hardcoded - every threshold, path, and knob lives in `config/`:

- `settings.yaml` - market hours, snapshot retention/Top N, change-detection
  thresholds, Claude/enrichment/email/logging settings.
- `scoring.yaml` - momentum scoring rules (`threshold_high_medium`,
  `threshold_single`, `range`). Adding a new scoring factor is a YAML edit.
- `prompts.yaml` - the Claude system/user prompt templates.
- `market_holidays.yaml` - NYSE full-day closures; update yearly.
- `.env` - secrets only (Finviz URL, API keys, SMTP credentials).

## Testing

```bash
venv\Scripts\python -m pytest tests/ -v
```

All tests use hand-built fixtures - none require a live browser, network
call, or real credentials.

## Roadmap

- ✅ Stage 1-5: Playwright login/scrape, config-driven scoring, change
  detection, Claude analysis (via OpenRouter), HTML reports, email.
- ✅ Stage 6: News corroboration (CORROBORATED/CONFLICTING/INCONCLUSIVE
  verdicts) and Fibonacci retracement levels enrich the Claude prompt and
  report for changed/top-ranked stocks.
- ✅ Unattended scheduling: `runner.py`/cron-driven 15-minute cycle, NYSE-
  precise and holiday-aware via `utils/market_calendar.py`.
- ✅ Codebase audit pass: shared `PipelineError` hierarchy, external-call
  timeouts, batched price-history fetches, snapshot retention actually
  wired in, and coverage for every non-trivial previously-untested module.
- ⏳ Future (Stage 9): backtesting/performance tracking against the
  historical snapshots already being persisted in `data/snapshots/`.
