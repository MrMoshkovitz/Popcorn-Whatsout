# Popcorn — What's Out?

Personal movie & TV tracker: Netflix CSV import, TMDB matching, recommendations, new-season alerts, and streaming availability — all in one dashboard with Telegram push notifications.

## Features

- **Netflix CSV Import** — upload your viewing history, auto-match to TMDB
- **Two-Pass Language Search** — Hebrew (he-IL) first, English (en-US) fallback
- **Recommendations** — TMDB-powered suggestions (5 movie / 3 TV per title)
- **New Season Alerts** — daily checks for new seasons of shows you watch
- **Streaming Availability** — see where titles are streaming in Israel
- **Telegram Notifications** — push alerts for new seasons, recommendations, and disambiguation
- **BiDi Support** — full Hebrew/English mixed content support

## Quick Start

1. **Clone and install:**
   ```bash
   git clone https://github.com/MrMoshkovitz/Popcorn-Whatsout.git
   cd Popcorn-WhatsOut
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your TMDB API key and Telegram bot token
   ```

3. **Initialize database:**
   ```bash
   sqlite3 popcorn.db < db/schema.sql
   ```

4. **Run the dashboard:**
   ```bash
   python dashboard/app.py
   ```
   Open http://localhost:5000 in your browser.

## Running the Telegram Bot

The bot runs as a separate process from the dashboard:

```bash
# Terminal 1 — Dashboard
python dashboard/app.py

# Terminal 2 — Telegram Bot
python bot/run_bot.py
```

Bot commands: `/start`, `/recommendations`, `/help`

## Key Commands

```bash
python dashboard/app.py          # Run the dashboard
python bot/run_bot.py            # Run the Telegram bot
pytest tests/                    # Run tests
python cron/daily_check.py       # Run daily cron manually
sqlite3 popcorn.db < db/schema.sql  # Initialize database
```

## Tech Stack

- **Python 3.11+**
- **Flask** — server-rendered dashboard with Jinja2 templates
- **SQLite** — single-file database (`popcorn.db`)
- **requests** — TMDB API client
- **python-telegram-bot** — push notifications
- **python-dateutil** — date parsing
- **Pico CSS** — classless CSS framework (CDN)

## Environment Variables

| Variable | Description |
|----------|-------------|
| `TMDB_API_KEY` | Your TMDB API v3 key |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from @BotFather |
| `TELEGRAM_ADMIN_CHAT_ID` | Your Telegram chat ID for notifications |

## Attribution

This product uses the [TMDB API](https://www.themoviedb.org/documentation/api) but is not endorsed or certified by TMDB.
