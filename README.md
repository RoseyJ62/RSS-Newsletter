# Executive News Digest

A lightweight, backend-only Python application that pulls headlines from structured news feeds, formats them into an executive-style digest, and emails it on demand or on a daily/weekly schedule.

The app does not call external news or AI APIs. It uses the Python standard library for the core workflow and includes the lightweight `tzdata` package on Windows so named time zones such as `America/Chicago` work reliably.

## Features

- Pulls headlines from RSS or Atom feeds
- Deduplicates and ranks recent items
- Produces plain-text and HTML executive digests
- Sends email through any SMTP server
- Runs once from the CLI or continuously on a daily/weekly schedule
- Optionally summarizes locally through a configurable command such as Ollama, disabled by default

## Quick Start

Requires Python 3.11+.

```powershell
python -m news_digest init-config
```

Edit `config.toml`, then validate it:

```powershell
python -m news_digest validate-config --config config.toml
```

Preview a digest without emailing:

```powershell
python -m news_digest run-once --config config.toml --dry-run
```

Send the digest:

```powershell
python -m news_digest run-once --config config.toml
```

Run the built-in scheduler:

```powershell
python -m news_digest schedule --config config.toml
```

## Configuration

See `config.example.toml`.

The default sources are RSS/Atom feeds. These are structured website feeds, not external APIs. Add or remove sources by editing the `[[sources]]` blocks.

SMTP credentials may be supplied directly in `config.toml`, but environment variables are recommended:

```toml
[email]
smtp_password_env = "NEWS_DIGEST_SMTP_PASSWORD"
```

Then set the variable in your shell or service manager.

## Local AI Summarization

Local AI support is disabled by default. When enabled, the app sends the digest draft to a local command over stdin and uses stdout as the executive summary.

Example with Ollama:

```toml
[ai]
enabled = true
command = ["ollama", "run", "llama3.2"]
timeout_seconds = 60
```

The app never calls hosted AI APIs.

## Scheduling

Daily:

```toml
[schedule]
enabled = true
frequency = "daily"
time = "07:30"
timezone = "America/Chicago"
```

Weekly:

```toml
[schedule]
enabled = true
frequency = "weekly"
day = "monday"
time = "07:30"
timezone = "America/Chicago"
```

For production, run `python -m news_digest schedule --config config.toml` under systemd, Task Scheduler, Docker, or another process supervisor.
