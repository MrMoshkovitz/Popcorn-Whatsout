# Popcorn Operations Guide

Everything you need to run, maintain, and use Popcorn.

---

## 1. Running the Dashboard

```bash
python dashboard/app.py
```

- Starts Flask on `http://localhost:5000` with debug mode enabled
- Auto-applies pending database migrations on startup
- No CLI flags — port and debug are hardcoded in `app.py`

### Dashboard Pages

| URL | What it does |
|-----|-------------|
| `/` | Redirects to `/watch-next` |
| `/watch-next` | Hero banner + recommendations sorted by match score, grouped by genre |
| `/coming-soon` | Timeline view grouped by month — upcoming seasons + franchise sequels |
| `/library` | Full library with stats bar (total/TV/movies/since), progress bars on TV cards |
| `/review` | Low-confidence TMDB matches needing manual correction |

### Dashboard Actions

| Action | How |
|--------|-----|
| Upload Netflix CSV | Library page > drag-drop zone or click to browse (24h rate limit) |
| Add title manually | Library page > search box, pick from autocomplete, set seasons + who watched |
| Dismiss recommendation | Hover card > "Dismiss" button (inline, no page reload) |
| Mark as watched | Hover card > "Watched" button (inline) |
| Undo dismiss | Toast notification > "Undo" link (5 second window) |
| View details | Click any card > modal with cast, trailer, seasons, similar titles |
| Edit title | Library > hover card > "Edit" > change TMDB match, seasons, who watched |
| Delete title | Library > hover card > "Delete" (confirms first) |
| Clear library | Library page bottom > "Clear Library" (deletes everything) |
| Bulk accept reviews | Review page > "Accept All (confidence >= 45%)" button |

### Filters (available on all pages)

| Filter | Where |
|--------|-------|
| Me / Wife / All | Nav bar (global) + filter bar (per-page) |
| Movies / TV / All | Watch Next, Coming Soon, Library filter bars |
| Genre filter | Watch Next only |
| Provider filter | Watch Next only |
| Search | All pages — filters cards by title text |
| Sort | Watch Next (relevance/title), Library (last watched/title/recently added) |

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/search?q=` | GET | TMDB autocomplete, returns top 5 results as JSON |
| `/api/detail/<type>/<tmdb_id>` | GET | Cast, trailer, similar titles for detail modal |
| `/api/taste-profile` | GET | User's genre distribution, avg rating, decades, type split |
| `/api/mark-watched/<rec_id>` | POST | Mark recommendation as watched (JSON response) |
| `/api/tag/<title_id>` | POST | Change user_tag inline (form param: `user_tag`) |
| `/dismiss/<rec_id>` | POST | Dismiss rec (JSON if `Accept: application/json`, else redirect) |
| `/undismiss/<rec_id>` | POST | Undo dismiss |

---

## 2. Running the Telegram Bot

```bash
python bot/telegram_notifier.py
```

- Starts in long-polling mode — keeps running until you stop it
- Requires `TELEGRAM_BOT_TOKEN` in `.env`
- First user to send `/start` gets their `chat_id` stored for push notifications

### Telegram Commands

| Command | What it does |
|---------|-------------|
| `/start` | Connect this chat for notifications, stores chat_id |
| `/help` | List all available commands |
| `/recommendations` | Show top 5 unseen recommendations with posters + streaming info |
| `/add <title>` | Search TMDB, pick from 3 results via inline keyboard, adds to library |
| `/search <title>` | Get TMDB recommendations for any title (not just your library) |
| `/upcoming <title>` | Check next season/sequel info for a title |
| `/similar <title>` | Find similar titles scored by genre overlap |
| `/mystats` | View library statistics (total titles, type breakdown, pending recs) |

### Inline Keyboard Callbacks

When the bot sends buttons, tapping them triggers:

| Callback | Action |
|----------|--------|
| `add_{tmdb_id}_{type}` | Add selected title to library |
| `watched_{tmdb_id}` | Mark series as fully watched |
| `remind_{tmdb_id}` | Dismiss alert, keep in Coming Soon |
| `disambig_{title_id}_{tmdb_id}` | Resolve ambiguous TMDB match |

### Push Notifications (sent automatically)

| Notification | When |
|-------------|------|
| New season alert | Daily cron detects a new released season (with poster photo) |
| New recommendations | Monday cron generates recs (top 5 by match score) |
| Weekly digest | Sunday cron summarizes new recs, coming soon, new titles |
| Admin alert | 3+ consecutive TMDB errors during daily cron |

---

## 3. Running the Backfill

```bash
python engine/backfill.py
```

Runs three backfill operations sequentially:

| Operation | What it does | TMDB calls | Duration |
|-----------|-------------|------------|----------|
| `backfill_genres()` | Fills NULL `genres` on titles + recommendations | 1 per item | ~0.2s each |
| `backfill_enrichment()` | Fills NULL `overview`, `backdrop_path`, `vote_average`, `release_year` | 1 per item | ~0.2s each |
| `backfill_franchises()` | Populates `franchise_tracking` for all movies with collections | 2 per movie | ~0.4s each |

**When to run:**
- After first CSV upload (titles have genres but may lack overview/backdrop)
- After schema migration adds new columns
- After manually adding many titles via Telegram `/add`
- Safe to re-run — only fetches for NULL values

**Duration estimate:** ~0.2 seconds per title/rec (TMDB rate limit). 300 titles + 900 recs = ~4 minutes.

### Individual backfill functions

You can run specific backfills from Python:

```python
import sqlite3
from config import DB_PATH
from engine.backfill import backfill_genres, backfill_enrichment, backfill_franchises

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

backfill_genres(conn)        # Just genres
backfill_enrichment(conn)    # Just overview/backdrop/rating/year
backfill_franchises(conn)    # Just franchise tracking

conn.close()
```

---

## 4. Running the Daily Cron

```bash
python cron/daily_check.py
```

Runs 7 phases sequentially:

| Phase | What | When |
|-------|------|------|
| 1 | Check new seasons for tracked series | Daily |
| 1b | Check movie franchises for unreleased sequels | Daily |
| 2 | Refresh streaming availability (IL region) | Daily |
| 3 | Generate recommendations + score + purge library dupes | **Monday only** |
| 4 | Auto-resolve stale review items (>48h, pick highest popularity) | Daily |
| 5b | Send weekly digest via Telegram | **Sunday only** |
| 5 | Error check — admin alert if 3+ TMDB errors | Daily |

**Crontab setup:**
```
0 6 * * * cd /path/to/popcorn && python cron/daily_check.py >> logs/cron.log 2>&1
```

**Logs:** stdout + `logs/cron.log` (dual output)

---

## 5. Running Tests

```bash
python -m pytest tests/ -v
```

- Uses in-memory SQLite — no real database touched
- All TMDB calls mocked — no API key needed
- No `time.sleep` — mocked for speed

---

## 6. One-Time Operations

### Score all existing recommendations

```bash
python -c "
import sqlite3
from config import DB_PATH
from engine.taste_scorer import score_all_recommendations
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
score_all_recommendations(conn)
conn.close()
"
```

No TMDB calls — pure math on stored data. Takes seconds.

### Purge watched titles from recommendations

```bash
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

### Initialize a fresh database

```bash
sqlite3 popcorn.db < db/schema.sql
```

### Apply pending migrations

Happens automatically on Flask startup, but can be run manually:

```bash
python -c "
from db.migrate import apply_migrations
from config import DB_PATH
apply_migrations(DB_PATH)
"
```

---

## 7. Environment Variables

File: `.env` (root directory, never committed)

| Variable | Required | Purpose |
|----------|----------|---------|
| `TMDB_API_KEY` | Yes | TMDB API v3 key for all metadata |
| `TELEGRAM_BOT_TOKEN` | For bot | Telegram bot token from @BotFather |
| `TELEGRAM_ADMIN_CHAT_ID` | For alerts | Fallback chat ID for admin alerts |

Example `.env`:
```
TMDB_API_KEY=abc123
TELEGRAM_BOT_TOKEN=123456:ABC-DEF
TELEGRAM_ADMIN_CHAT_ID=987654
```

---

## 8. Match Score System

Recommendations are scored 0-99 across 5 dimensions:

| Dimension | Points | How |
|-----------|--------|-----|
| Genre overlap | 0-40 | How well rec's genres match your most-watched genres |
| Rating quality | 0-20 | TMDB vote_average (8.5 = 17 points) |
| Source affinity | 0-20 | How many episodes you watched of the source title |
| Recency | 0-10 | 2025+ = 10, 2020+ = 5, older = 2 |
| Streaming | 0-10 | Available on IL streaming = 10, not = 0 |

Display: green badge (70+), yellow badge (40-69), gray badge (1-39).

Sorting: Watch Next is sorted by `match_score DESC` — best matches first.
