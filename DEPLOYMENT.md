# Deployment

The pipeline is deterministic: given the same inputs (Finviz screener state,
market clock) it does the same thing every time. Nothing here is an agent or
LLM decision - Claude is only ever called *inside* a run to analyze already-
selected stocks, never to decide whether or when to run. Both options below
just trigger `python app.py --once` on a schedule; the market-hours/holiday
gate (`utils/market_calendar.py`) lives inside that call either way, so a
trigger that fires too early, too often, or on a weekend is always a safe
no-op.

## Option A: systemd (persistent process)

Runs `runner.py`, which starts once and ticks every 15 minutes for as long as
the process lives.

`/etc/systemd/system/finviz-scanner.service`:

```ini
[Unit]
Description=Finviz AI Trading Intelligence Platform
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/finviz-ai-scanner
ExecStart=/opt/finviz-ai-scanner/venv/bin/python runner.py
Restart=on-failure
RestartSec=30
EnvironmentFile=/opt/finviz-ai-scanner/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now finviz-scanner
sudo journalctl -u finviz-scanner -f   # tail systemd's own stdout/stderr capture
tail -f /opt/finviz-ai-scanner/logs/app.log   # tail the app's own Loguru output
```

`Restart=on-failure` brings the process back if it crashes; `WantedBy=multi-
user.target` + `enable` starts it on boot. Adjust `WorkingDirectory`/
`ExecStart`/`EnvironmentFile` paths to wherever the repo and venv actually live.

## Option B: cron (no persistent process)

Runs a fresh `python app.py --once` invocation on a timer - nothing stays
resident between runs.

```cron
*/15 9-16 * * 1-5 cd /opt/finviz-ai-scanner && TZ=America/New_York venv/bin/python app.py --once >> logs/cron.log 2>&1
```

The cron hour range (`9-16`) is intentionally coarse - it doesn't need to know
about the `:30` open or NYSE holidays, because `MarketHoursGuard` inside
`run_once()` is the real, precise, holiday-aware gate. Cron's only job is
"wake up roughly often enough"; the app decides whether to actually do
anything.

## Which one to use

|                          | systemd + runner.py                          | cron + `app.py --once`                    |
|--------------------------|-----------------------------------------------|--------------------------------------------|
| State between runs       | Possible in principle (same process, though this implementation doesn't currently cache anything across ticks - each tick still calls the same `run_once()` fresh) | None - every run is a brand-new process |
| What's "alive" to monitor | One long-lived process (needs `systemctl status`/crash monitoring) | Nothing persistent - only cron itself, which the OS already manages |
| Startup cost per run      | Same as cron today (settings reload, new browser launch each tick) - see above | New Python process + settings reload + new browser launch every time |
| Self-healing              | Relies on `Restart=on-failure`               | Automatic - a failed run just doesn't affect the next scheduled one |
| Best for                  | A server you're already keeping up (want single-command status/log tailing) | Anyone who'd rather not manage a persistent service at all |

Both call the exact same `run_once()` function, so behavior is identical
either way - this is purely a process-management choice, not a functional one.

## Logging

Loguru writes to `logs/app.log` with daily rotation (`config/settings.yaml`
`logging.rotation: "00:00"`) and 14-day retention. When tailing the log:

- `MARKET CLOSED - skipping this run (no-op).` - normal, expected outside
  NYSE regular hours or on a holiday/weekend. Not a problem.
- Any `ERROR` line - an actual failure (Finviz login/download, Claude API,
  email, etc.), already caught and logged per-step so the process/next
  scheduled run isn't affected. Worth investigating if it repeats.

If you're tailing this log to confirm the deployment is "alive," seeing
periodic `MARKET CLOSED` lines overnight/on weekends is exactly what a
healthy deployment looks like - it means the schedule is firing and the gate
is working, not that something is broken.
