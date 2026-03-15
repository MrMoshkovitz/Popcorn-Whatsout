# Popcorn — Complete Documentation

**Personal movie & TV tracker.** Netflix CSV import, TMDB-powered recommendations, new season alerts, streaming availability (Israel), dashboard + Telegram notifications. Single user. Zero effort after first upload.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Installation](#2-installation)
3. [Configuration](#3-configuration)
4. [Database Setup](#4-database-setup)
5. [First Run](#5-first-run)
6. [Importing Your Netflix History](#6-importing-your-netflix-history)
7. [Dashboard Guide](#7-dashboard-guide)
8. [Telegram Bot Setup](#8-telegram-bot-setup)
9. [Automated Daily Updates](#9-automated-daily-updates)
10. [Data Backfill](#10-data-backfill)
11. [Architecture Overview](#11-architecture-overview)
12. [Database Schema](#12-database-schema)
13. [API Reference](#13-api-reference)
14. [Match Scoring System](#14-match-scoring-system)
15. [Maintenance & Operations](#15-maintenance--operations)
16. [Troubleshooting](#16-troubleshooting)
17. [Security Considerations](#17-security-considerations)

---

## 1. Prerequisites

| Requirement | Version | Purpose |
|------------|---------|---------|
| Python | 3.11+ | Runtime |
| pip | any | Package manager |
| SQLite | 3.x (bundled with Python) | Database |
| TMDB API key | v3 | All metadata, recommendations, streaming data |
| Telegram bot token | (optional) | Push notifications |

### Getting a TMDB API Key

1. Create account at [themoviedb.org](https://www.themoviedb.org/signup)
2. Go to Settings > API > Request an API Key
3. Choose "Developer" > fill the form (personal use is fine)
4. Copy the **API Key (v3 auth)** — not the access token

### Getting a Telegram Bot Token (optional)

1. Open Telegram, search for `@BotFather`
2. Send `/newbot`, follow prompts to name your bot
3. Copy the token (format: `123456789:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)
4. Send `/start` to your new bot to activate it

---

## 2. Installation

```bash
# Clone the repository
git clone https://github.com/MrMoshkovitz/Popcorn-Whatsout.git
cd Popcorn-Whatsout

# Create virtual environment (recommended)
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Dependencies (4 total)

| Package | Purpose |
|---------|---------|
| `flask>=3.0` | Web framework, server-rendered dashboard |
| `requests>=2.31` | HTTP client for TMDB API |
| `python-telegram-bot>=20.0` | Telegram bot (push notifications + commands) |
| `python-dateutil>=2.8` | Date parsing for Netflix CSV (handles DD/MM/YYYY) |

### Dev Dependencies (not in requirements.txt)

```bash
pip install pytest  # Test runner
```

---

## 3. Configuration

```bash
# Copy the example environment file
cp .env.example .env
```

Edit `.env` with your keys:

```ini
TMDB_API_KEY=your_actual_tmdb_api_key
TELEGRAM_BOT_TOKEN=your_actual_bot_token
TELEGRAM_ADMIN_CHAT_ID=your_chat_id
```

| Variable | Required | Description |
|----------|----------|-------------|
| `TMDB_API_KEY` | **Yes** | TMDB API v3 key. Without this, nothing works. |
| `TELEGRAM_BOT_TOKEN` | No | Enables Telegram bot. Without it, dashboard still works fully. |
| `TELEGRAM_ADMIN_CHAT_ID` | No | Fallback chat ID for error alerts. Auto-set when you `/start` the bot. |

### Configuration Constants (config.py)

These are hardcoded and rarely need changing:

| Constant | Value | Purpose |
|----------|-------|---------|
| `TMDB_BASE_URL` | `https://api.themoviedb.org/3` | API endpoint |
| `TMDB_LANGUAGE_PRIMARY` | `he-IL` | First language for searches (Hebrew) |
| `TMDB_LANGUAGE_FALLBACK` | `en-US` | Fallback if Hebrew returns no results |
| `WATCH_REGION` | `IL` | Streaming availability region (Israel) |
| `API_DELAY_SECONDS` | `0.2` | Rate limit between TMDB calls |
| `MATCH_CONFIDENCE_THRESHOLD` | `0.45` | Below this, titles go to Review queue |
| `DISAMBIGUATION_TIMEOUT_HOURS` | `48` | Auto-resolve unreviewed matches after 48h |

---

## 4. Database Setup

```bash
# Initialize an empty database
sqlite3 popcorn.db < db/schema.sql
```

This creates `popcorn.db` with 8 tables. The database is a single file — back it up by copying it.

Migrations are applied automatically when the Flask app starts. You can also run them manually:

```bash
python -c "from db.migrate import apply_migrations; from config import DB_PATH; apply_migrations(DB_PATH)"
```

---

## 5. First Run

```bash
# Start the dashboard
python dashboard/app.py
```

Open `http://localhost:5000` in your browser. You'll see an empty library with:
- Upload zone for Netflix CSV
- Manual add search box
- Three tabs: Watch Next, Coming Soon, Library

---

## 6. Importing Your Netflix History

### Step 1: Export from Netflix

1. Go to [netflix.com/account](https://www.netflix.com/account)
2. Click **Profile** (top right) > **Account**
3. Scroll to **Security & Privacy** > **Download your personal information**
4. Request data, wait for email (usually minutes, sometimes hours)
5. Download the ZIP, extract it
6. Find `CONTENT_INTERACTION/ViewingActivity.csv`

### Step 2: Upload to Popcorn

1. Open `http://localhost:5000/library`
2. Drag the CSV file onto the upload zone (or click to browse)
3. Select **Who watched**: Both / Me / Wife
4. Click **Upload**

### What Happens During Upload

1. **CSV Parsing** — each row is split by `: ` (colon-space). First segment = title name, looks for "Season X" or Hebrew equivalent, remaining = episode name
2. **Deduplication** — unique title names extracted (reduces API calls dramatically)
3. **TMDB Matching** — each unique name searched on TMDB: Hebrew first, English fallback. Confidence scored by name similarity (70%) + popularity (30%)
4. **Database Insert** — titles, watch history, series tracking populated
5. **Recommendation Generation** — TMDB recommendations fetched for each title
6. **Scoring** — all recommendations scored by 5-dimension match algorithm
7. **Purge** — any recommendation that matches an existing library title is removed

**Rate limit:** one upload per 24 hours. The CSV is deleted after processing.

### Step 3: Review Low-Confidence Matches

After upload, check the **Review** tab (shows count in nav). These are titles where TMDB matching confidence was below 45%.

Options:
- **Accept Match** — the guess is correct
- **Search & Replace** — search for the correct title using autocomplete
- **Batch Accept** — set a confidence threshold (e.g., 20%) and accept all above it at once

---

## 7. Dashboard Guide

### Watch Next (`/watch-next`)

The main screen. Shows what to watch tonight.

**Hero Banner** — cinematic full-width backdrop of top 3 recommendations. Auto-rotates every 8 seconds. Click dots to navigate.

**Sections:**
- **Continue Watching** — TV shows where you've watched some seasons but more are available now
- **Franchise Catch-up** — movie collection parts you haven't seen (e.g., watched Dark Knight but not Batman Begins)
- **[Genre] Movies For You** — recommendations grouped by genre, sorted by match score
- **[Genre] Series For You** — same for TV

**Card Features:**
- Rating badge (top-left, gold)
- Type badge (top-right, green=TV / blue=Movie)
- Match % badge (green 70+, yellow 40-69, gray <40)
- Provider logos overlay (bottom of poster)
- Hover: description text + Dismiss / Watched buttons
- Click: detail modal with cast, YouTube trailer, season checklist, similar titles

**Filters:**
- All / Movies / TV (type)
- All / Me / Wife (who watched)
- Genre filter pills
- Provider filter pills
- Text search
- Sort: Relevance / Title A-Z

**Inline Actions (no page reload):**
- Dismiss → card fades out → toast with Undo (5s)
- Mark Watched → card fades out → toast confirms

### Coming Soon (`/coming-soon`)

Upcoming content, grouped by month in a timeline view.

**TV Alerts:**
- Shows where next season hasn't aired yet
- Countdown badges: "This week!" (green, <=7 days), "In X days" (gold, <=30 days), date, or "TBA"
- "Returning" badge for shows confirmed to continue

**Franchise Alerts:**
- Unreleased sequel movies in collections you've watched

### Library (`/library`)

Your complete collection.

**Stats Bar** (top) — Total titles, TV shows, Movies, Since (earliest watch year)

**Cards include:**
- Rating badge, type badge
- Season progress bar for TV (e.g., S2/5 = 40% filled)
- Year + genre metadata
- Click for detail modal
- Hover for Edit / Delete

**Actions:**
- Upload CSV (drag-drop zone)
- Add title manually (autocomplete search)
- Edit title (change TMDB match, watched seasons, who watched)
- Delete title (removes all related data)
- Clear Library (nuclear option — confirms first)

**Filters:** type, tag (me/wife), search, sort (last watched / title / recently added)

### Review (`/review`)

Low-confidence TMDB matches. Each card shows:
- Poster of current guess
- Raw CSV title vs TMDB guess
- Confidence percentage
- Accept / Search-to-replace

**Batch Accept:** input field to set minimum confidence %, accepts all above that threshold at once.

### Detail Modal (all pages)

Click any card to open. Shows:
- Full backdrop image (16:9)
- Title, year, rating, genre pills
- Full overview/description
- **Cast** — headshot photos + names (horizontal scroll)
- **Trailer** — embedded YouTube player
- **Seasons** (TV only) — checklist showing watched vs unwatched
- **Similar Titles** — clickable poster row (opens new modal)

Close: click X, click outside, or press Escape.

### Mobile Experience

On screens under 768px:
- Fixed bottom navigation replaces top tabs (Watch, Soon, Library, Review)
- Detail modal slides up as bottom sheet (85vh)
- Poster grid switches to 2-column layout
- Toast notifications appear above bottom nav

---

## 8. Telegram Bot Setup

### Starting the Bot

```bash
python bot/telegram_notifier.py
```

Runs in long-polling mode (keeps running in foreground). For background:

```bash
nohup python bot/telegram_notifier.py >> logs/bot.log 2>&1 &
```

### Connecting Your Chat

1. Open Telegram, find your bot by name
2. Send `/start`
3. Bot responds with confirmation and stores your chat_id

### Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/start` | Connect chat for push notifications | `/start` |
| `/help` | List all commands | `/help` |
| `/recommendations` | Top 5 unseen recs with posters + streaming info | `/recommendations` |
| `/add <title>` | Search TMDB, pick from results, adds to library | `/add Breaking Bad` |
| `/search <title>` | Get TMDB recs for any title (not just library) | `/search Inception` |
| `/upcoming <title>` | Next season/sequel info | `/upcoming Stranger Things` |
| `/similar <title>` | Similar titles scored by genre overlap | `/similar The Office` |
| `/mystats` | Library statistics | `/mystats` |

### Automatic Notifications

| Type | Trigger | Content |
|------|---------|---------|
| New Season Alert | Daily cron detects released season | Poster photo + "Season X available" + Mark Watched / Remind Later buttons |
| New Recommendations | Monday cron generates recs | Top 5 recs by match score |
| Weekly Digest | Sunday cron | Summary: new recs count, coming soon count, new titles |
| Admin Error Alert | 3+ consecutive TMDB errors in cron | Error details + timestamp |

---

## 9. Automated Daily Updates

### The Daily Cron

```bash
python cron/daily_check.py
```

Runs 7 phases sequentially:

| Phase | Name | Schedule | What it does |
|-------|------|----------|-------------|
| 1 | New Seasons | Daily | Checks TMDB for new seasons of tracked series |
| 1b | Franchises | Daily | Checks movie collections for unreleased sequels |
| 2 | Streaming | Daily | Refreshes IL streaming providers for all titles |
| 3 | Recommendations | **Monday only** | Generates new recs + scores + purges library dupes |
| 4 | Disambiguation | Daily | Auto-resolves review items older than 48h |
| 5b | Weekly Digest | **Sunday only** | Sends summary notification via Telegram |
| 5 | Error Check | Daily | Sends admin alert if 3+ TMDB errors occurred |

### Setting Up Crontab

```bash
# Run daily at 6 AM
crontab -e
```

Add:
```
0 6 * * * cd /path/to/Popcorn-Whatsout && /path/to/venv/bin/python cron/daily_check.py >> logs/cron.log 2>&1
```

### Logs

- **stdout** — real-time phase progress
- **logs/cron.log** — persistent log with timestamps

Each phase logs: start time, items processed, errors, duration.

---

## 10. Data Backfill

For enriching existing data with additional metadata (overview, backdrop images, ratings, genres, franchise info).

```bash
python engine/backfill.py
```

Runs three operations:

| Operation | Purpose | API Calls | When to Run |
|-----------|---------|-----------|-------------|
| `backfill_genres()` | Fill NULL genres on titles + recs | 1 per item with NULL genres | After schema changes |
| `backfill_enrichment()` | Fill overview, backdrop, vote_average, release_year | 1 per item with NULL values | After migration 005+ |
| `backfill_franchises()` | Populate franchise_tracking for movie collections | 2 per movie | After first import |

**Duration:** ~0.2 seconds per API call (TMDB rate limit). 300 titles + 900 recs = ~4 minutes.

**Safe to re-run** — only fetches data for NULL values, skips already-populated rows.

### Individual Operations

```bash
# Score all recommendations (no API calls, pure math, seconds)
python -c "
import sqlite3
from config import DB_PATH
from engine.taste_scorer import score_all_recommendations
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
score_all_recommendations(conn)
conn.close()
"

# Purge watched titles from recommendations (no API calls)
python -c "
import sqlite3
from config import DB_PATH
from engine.recommendations import purge_library_recommendations
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
purge_library_recommendations(conn)
conn.close()
"
```

---

## 11. Architecture Overview

```
                    Netflix CSV
                        │
                        ▼
                 ┌──────────────┐
                 │  csv_parser  │  Parse rows, extract title/season/date
                 └──────┬───────┘
                        │
                        ▼
                 ┌──────────────┐
                 │ tmdb_matcher │  Two-pass search (he-IL → en-US)
                 │              │  Confidence scoring, deduplication
                 └──────┬───────┘
                        │
              ┌─────────┼─────────┐
              ▼         ▼         ▼
         ┌────────┐ ┌────────┐ ┌──────────────┐
         │ titles │ │ watch_ │ │   series_    │
         │        │ │history │ │  tracking    │
         └───┬────┘ └────────┘ └──────────────┘
             │
    ┌────────┼────────────────┐
    ▼        ▼                ▼
┌────────┐ ┌──────────┐ ┌─────────────┐
│  recs  │ │streaming │ │  franchise  │
│ engine │ │  avail.  │ │  checker    │
└───┬────┘ └──────────┘ └─────────────┘
    │
    ▼
┌────────────┐     ┌────────────┐
│  Flask     │     │  Telegram  │
│ Dashboard  │     │    Bot     │
│ (5 pages)  │     │ (8 cmds)  │
└────────────┘     └────────────┘
    ▲                     ▲
    │                     │
    └───── daily_check ───┘
          (7 phases)
```

### File Structure

```
Popcorn-Whatsout/
├── config.py                    # Environment loader, all constants
├── .env                         # Secrets (not committed)
├── .env.example                 # Template
├── requirements.txt             # 4 packages
├── popcorn.db                   # SQLite database (not committed)
│
├── db/
│   ├── schema.sql               # 8 tables, indexes, constraints
│   ├── migrate.py               # SQL migration runner
│   └── migrations/              # Sequential .sql files (001-006)
│
├── ingestion/
│   ├── csv_parser.py            # Netflix CSV → ParsedEntry dicts
│   ├── tmdb_matcher.py          # ParsedEntry → matched titles via TMDB
│   └── tmdb_api.py              # Shared TMDB HTTP helper (rate-limited)
│
├── engine/
│   ├── recommendations.py       # Generate + purge TMDB recommendations
│   ├── taste_scorer.py          # 5-dimension match scoring (0-99)
│   ├── new_season_checker.py    # Detect new seasons for tracked series
│   ├── availability.py          # Streaming providers (IL region)
│   ├── franchise_checker.py     # Movie collection tracking
│   ├── genre_map.py             # TMDB genre ID → name mapping
│   └── backfill.py              # Batch enrichment (genres, metadata, franchises)
│
├── dashboard/
│   ├── app.py                   # Flask app, all routes
│   ├── templates/
│   │   ├── base.html            # Layout, nav, modal, toast, bottom nav
│   │   ├── watch_next.html      # Hero banner + genre-grouped recs
│   │   ├── coming_soon.html     # Timeline view by month
│   │   ├── library.html         # Stats bar + grid + upload + add
│   │   ├── review.html          # Low-confidence matches + batch accept
│   │   └── edit.html            # Edit title details
│   └── static/
│       └── style.css            # Full cinematic dark theme (~850 lines)
│
├── bot/
│   └── telegram_notifier.py     # 8 commands + 4 push functions + callbacks
│
├── cron/
│   └── daily_check.py           # 7-phase daily orchestrator
│
├── tests/
│   ├── conftest.py              # Shared fixtures (in-memory DB)
│   ├── test_csv_parser.py       # 6 tests
│   ├── test_tmdb_matcher.py     # 8 tests
│   ├── test_recommendations.py  # 8 tests
│   ├── test_dashboard.py        # 20+ tests
│   ├── test_telegram.py         # 14 tests
│   └── ...                      # 78 tests total
│
├── guides/
│   ├── operations.md            # Quick reference for all commands
│   ├── netflix_export_guide_en.md
│   └── netflix_export_guide_he.md
│
├── docs/
│   └── getting-started.md       # This file
│
└── logs/
    └── cron.log                 # Daily cron output
```

---

## 12. Database Schema

8 tables in `popcorn.db`:

### titles
Core metadata for every movie/TV show in the library.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Internal ID |
| tmdb_id | INTEGER | TMDB identifier |
| tmdb_type | TEXT | `movie` or `tv` |
| title_en | TEXT | English title |
| title_he | TEXT | Hebrew title |
| poster_path | TEXT | TMDB poster image path |
| original_language | TEXT | ISO language code |
| confidence | REAL | TMDB match confidence (0.0 - 1.0) |
| match_status | TEXT | `auto`, `review`, or `manual` |
| source | TEXT | `csv` or `manual` |
| user_tag | TEXT | `me`, `wife`, or `both` |
| genres | TEXT | JSON array of genre names |
| overview | TEXT | Plot description |
| backdrop_path | TEXT | TMDB backdrop image path |
| vote_average | REAL | TMDB rating (0-10) |
| release_year | TEXT | Year of release |

### watch_history
Individual viewing records from Netflix CSV.

### series_tracking
TV series progress — seasons watched vs available, next air dates.

### recommendations
TMDB-sourced recommendations with match scoring.

| Key columns | Description |
|-------------|-------------|
| match_score | 0-99 computed score (see Section 14) |
| status | `unseen`, `dismissed`, `watched` |
| collection_name | Non-null for franchise catch-up recs |

### streaming_availability
Provider info for IL region (Netflix, Disney+, etc.)

### franchise_tracking
Movie collection tracking (e.g., MCU, Dark Knight trilogy).

### settings
Key-value store (last_upload_date, telegram_chat_id).

### schema_migrations
Tracks applied SQL migrations.

---

## 13. API Reference

### Dashboard Routes

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Redirect to `/watch-next` |
| GET | `/watch-next` | Recommendations with hero banner |
| GET | `/coming-soon` | Upcoming seasons/sequels timeline |
| GET | `/library` | Full library with stats |
| GET | `/review` | Low-confidence matches |
| POST | `/upload` | CSV upload (24h rate limit) |
| GET | `/search?q=` | TMDB autocomplete (JSON, top 5) |
| POST | `/add` | Add title from autocomplete |
| POST | `/resolve/<title_id>` | Confirm/change TMDB match |
| POST | `/dismiss/<rec_id>` | Dismiss recommendation |
| POST | `/undismiss/<rec_id>` | Undo dismiss |
| POST | `/bulk-accept` | Batch accept reviews (param: `threshold`) |
| GET | `/edit/<title_id>` | Edit title page |
| POST | `/edit/<title_id>` | Save title changes |
| POST | `/delete/<title_id>` | Delete title + all related data |
| POST | `/delete-all` | Clear entire library |

### JSON API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/detail/<type>/<tmdb_id>` | Cast, trailer, similar (for modal) |
| GET | `/api/taste-profile` | Genre distribution, avg rating, decades |
| POST | `/api/mark-watched/<rec_id>` | Mark rec as watched |
| POST | `/api/tag/<title_id>` | Change user_tag (param: `user_tag`) |

### Query Parameters

| Param | Used on | Values |
|-------|---------|--------|
| `tag` | All pages | `all`, `me`, `wife` — filters by who watched |
| `q` | `/search` | Search query (min 3 chars) |

---

## 14. Match Scoring System

Every recommendation is scored 0-99 across 5 dimensions:

| Dimension | Max Points | Calculation |
|-----------|-----------|-------------|
| **Genre Overlap** | 40 | How many of the rec's genres appear in your most-watched genres, weighted by frequency |
| **Rating Quality** | 20 | TMDB vote_average / 10 * 20 (e.g., 8.5 rating = 17 points) |
| **Source Affinity** | 20 | How many episodes you watched of the source title * 2, capped at 20 |
| **Recency** | 10 | 2025+ = 10pts, 2020-2024 = 5pts, older = 2pts |
| **Streaming** | 10 | Available on IL streaming = 10pts, not available = 0pts |

### Display

| Score | Badge Color | Meaning |
|-------|-------------|---------|
| 70-99 | Green | Strong match |
| 40-69 | Yellow | Moderate match |
| 1-39 | Gray | Weak match |

All recommendation lists are sorted by `match_score DESC`.

---

## 15. Maintenance & Operations

### Regular Tasks

| Task | Frequency | Method |
|------|-----------|--------|
| Update seasons + streaming | Daily | Cron (`daily_check.py`) |
| Generate new recommendations | Weekly (Monday) | Cron phase 3 |
| Review ambiguous matches | As needed | Dashboard `/review` |
| Upload new Netflix history | After binge sessions | Dashboard upload |

### Backup

```bash
# Database is a single file
cp popcorn.db popcorn.db.backup

# Or with timestamp
cp popcorn.db "popcorn_$(date +%Y%m%d).db"
```

### Reset Everything

```bash
# Delete database and start fresh
rm popcorn.db
sqlite3 popcorn.db < db/schema.sql
```

### Check Database Health

```bash
python -c "
import sqlite3
conn = sqlite3.connect('popcorn.db')
conn.row_factory = sqlite3.Row
print('Titles:', conn.execute('SELECT COUNT(*) FROM titles').fetchone()[0])
print('Watch history:', conn.execute('SELECT COUNT(*) FROM watch_history').fetchone()[0])
print('Recommendations:', conn.execute('SELECT COUNT(*) FROM recommendations WHERE status=\"unseen\"').fetchone()[0])
print('Reviews pending:', conn.execute('SELECT COUNT(*) FROM titles WHERE match_status=\"review\"').fetchone()[0])
print('Migrations:', [r[0] for r in conn.execute('SELECT filename FROM schema_migrations ORDER BY filename').fetchall()])
conn.close()
"
```

### Running Tests

```bash
# All tests (78 total)
python -m pytest tests/ -v

# Single file
python -m pytest tests/test_dashboard.py -v

# With output
python -m pytest tests/ -v -s
```

Tests use in-memory SQLite and mocked TMDB calls — no API key needed, no real database touched.

---

## 16. Troubleshooting

### "No recommendations showing"

1. Check you have titles: `/library` should show your imported titles
2. Run recommendation generation: `python -c "import sqlite3; from config import DB_PATH; from engine.recommendations import generate_all_recommendations; conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row; print(generate_all_recommendations(conn)); conn.close()"`
3. Score them: same pattern with `score_all_recommendations`

### "Hero banner not showing"

Hero requires recommendations with `backdrop_path`. Run the backfill: `python engine/backfill.py`

### "Cards look plain / no ratings"

Same — backfill populates `vote_average`, `overview`, `release_year`. Run `python engine/backfill.py`.

### "Upload says rate limited"

24-hour cooldown between uploads. To bypass (e.g., wrong file uploaded):
```bash
python -c "
import sqlite3
conn = sqlite3.connect('popcorn.db')
conn.execute(\"DELETE FROM settings WHERE key = 'last_upload_date'\")
conn.commit()
conn.close()
"
```

### "Telegram bot not responding"

1. Verify token: `python -c "from config import TELEGRAM_BOT_TOKEN; print('Token set:', bool(TELEGRAM_BOT_TOKEN))"`
2. Check if running: `ps aux | grep telegram_notifier`
3. Check logs: look for connection errors in terminal output

### "TMDB API errors"

1. Verify key: `python -c "from ingestion.tmdb_api import tmdb_get; print(tmdb_get('/movie/550'))"`
2. If returns None with errors → check API key in `.env`
3. Rate limiting is automatic (0.2s between calls)

---

## 17. Security Considerations

| Concern | Mitigation |
|---------|-----------|
| SQL injection | All queries use parameterized `?` placeholders. No string interpolation in SQL. |
| API key exposure | Keys in `.env`, loaded via `config.py`, `.env` in `.gitignore` |
| XSS | Jinja2 autoescaping enabled (Flask default). No `| safe` on user content. |
| File upload | Only `.csv` accepted. File deleted after processing. 24h rate limit. |
| Single user | No auth system — designed for personal/home use only. Don't expose to internet without a reverse proxy. |
| TMDB attribution | Footer with TMDB logo on every page (required by TMDB API terms). |
