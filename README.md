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

## Desktop App (News Digest Controller)

`main.py` launches a Tkinter window with four tabs:

- **Dashboard**: run the digest now, start or stop the built-in schedule, and jump to the other tabs.
- **Articles**: the latest digest, ranked by keyword relevance. Each card can be opened, saved (☆ Save / ★ Saved) and optionally rated. "How do ratings work?" explains what each rating does.
- **Saved Articles**: bookmarked articles with their title, link, summary, source and dates. Open the original or remove it. Saved articles are stored in `saved_articles.json` next to the app, so they survive restarts and stay available after they drop out of the feeds. Duplicates (same URL) are ignored.
- **Settings**: RSS feeds, schedule, and **Keyword Management** for the high-signal keywords in `osf_context.json`. Keywords can be added, edited and removed. Duplicates are blocked regardless of case or extra spaces, and nothing is written until you click Save Keywords.

**Ratings** use a 4-point scale: 1 Strongly dislike (-0.2), 2 Dislike (-0.1), 3 Like (+0.1), 4 Strongly like (+0.2). The value is added to the personal weight of each tracked keyword the article matched (minimum 0.1). Leaving an article unrated changes nothing. Older history entries without a `scale` field came from the previous 1–5 scale. Their effect is already included in the stored weights, so they are kept as they are and never re-applied. Weight keys are read case-insensitively.

Data files used by the desktop app: `config_local.json` (feeds and schedule), `osf_context.json` (scoring keywords), `user_profile.json` (keyword weights and rating history) and `saved_articles.json` (saved articles).
