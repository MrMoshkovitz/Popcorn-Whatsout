# 🍿 Popcorn — Simplified Architecture

**Technical blueprint. No over-engineering. Ship the toy.**

---

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│                      POPCORN v0.1                       │
│                                                         │
│  ┌───────────┐   ┌────────────┐   ┌──────────────────┐ │
│  │ CSV       │──▶│ TMDB       │──▶│ SQLite           │ │
│  │ Parser    │   │ Matcher    │   │ (single file)    │ │
│  └───────────┘   └────────────┘   └────────┬─────────┘ │
│                                        │   │   │       │
│                        ┌───────────────┘   │   └────┐  │
│                        ▼                   ▼        ▼  │
│                  ┌──────────┐   ┌────────────┐ ┌─────┐ │
│                  │Dashboard │   │ Daily Cron │ │ Bot │ │
│                  │(Flask)   │   │            │ │(TG) │ │
│                  └──────────┘   └────────────┘ └─────┘ │
│                                                         │
└─────────────────────────────────────────────────────────┘
              │                │              │
              ▼                ▼              ▼
          Browser         TMDB API      Telegram API
```

## Components

### 1. CSV Parser (`ingestion/csv_parser.py`)

**Input:** `NetflixViewingHistory.csv` (Title, Date — 2 columns)
**Output:** List of `ParsedEntry` objects

```
ParsedEntry:
  - raw_title: str          # Original string from CSV
  - parsed_name: str        # Extracted show/movie name (split on ":")
  - parsed_season: int|None # Extracted season number if present
  - parsed_episode: str|None# Extracted episode name if present
  - watch_date: date        # Parsed date (locale-aware)
  - is_likely_series: bool  # True if ":" split yielded season info
```

**Parsing logic:**
1. Split title on `:`
2. First segment → show/movie name
3. If second segment matches pattern `Season X` / `Part X` / `עונה X` → extract season number, mark as series
4. Remaining segments → episode name
5. If only one segment (no `:`) → treat as movie
6. Date parsing: `dateutil.parser.parse(date_str, dayfirst=True)`

**Edge cases accepted (not solved):**
- Movies with colons (e.g., "Mission: Impossible") → may be misidentified as series initially; TMDB search corrects this
- Hebrew season names not in the pattern list → treated as movie, corrected on TMDB search fallback

### 2. TMDB Matcher (`ingestion/tmdb_matcher.py`)

**Input:** List of `ParsedEntry`
**Output:** List of `MatchedTitle` with TMDB IDs

```
MatchedTitle:
  - tmdb_id: int
  - tmdb_type: "movie" | "tv"
  - title_en: str
  - title_he: str|None
  - poster_path: str|None
  - confidence: float       # Based on popularity + string similarity
  - match_status: "auto" | "review" | "manual"
  - source: "csv" | "manual"
```

**Matching algorithm (two-pass):**
```
IF is_likely_series:
    1. Search TMDB /search/tv?query={parsed_name}&language=he-IL
    2. If no results → /search/tv?query={parsed_name}&language=en-US
    3. If no results → search as movie (fallback)
ELSE:
    1. Search TMDB /search/movie?query={parsed_name}&language=he-IL
    2. If no results → /search/movie?query={parsed_name}&language=en-US
    3. If no results → search as TV (fallback)

PICK: Result #1 by TMDB popularity score
CONFIDENCE: popularity_score * string_similarity(query, result_title)
IF confidence < THRESHOLD (configurable, default 0.6):
    match_status = "review" (flagged for user in dashboard)
ELSE:
    match_status = "auto"
```

**Rate limiting:** 200ms delay between API calls. ~50 req/sec CDN limit. 2000 entries ≈ 7 minutes.

### 3. SQLite Database (`db/schema.sql`)

**Single file. No ORM. Raw SQL with parameterized queries.**

```sql
-- Core tables
CREATE TABLE titles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tmdb_id INTEGER NOT NULL,
    tmdb_type TEXT NOT NULL CHECK(tmdb_type IN ('movie', 'tv')),
    title_en TEXT,
    title_he TEXT,
    poster_path TEXT,
    confidence REAL DEFAULT 1.0,
    match_status TEXT DEFAULT 'auto' CHECK(match_status IN ('auto', 'review', 'manual')),
    source TEXT DEFAULT 'csv' CHECK(source IN ('csv', 'manual')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tmdb_id, tmdb_type)
);

CREATE TABLE watch_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title_id INTEGER REFERENCES titles(id),
    raw_csv_title TEXT,
    watch_date DATE NOT NULL,
    season_number INTEGER,
    episode_name TEXT,
    UNIQUE(title_id, watch_date, season_number, episode_name)
);

CREATE TABLE series_tracking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title_id INTEGER REFERENCES titles(id),
    tmdb_id INTEGER NOT NULL,
    total_seasons_tmdb INTEGER,          -- From TMDB
    max_watched_season INTEGER,          -- From user's history
    last_checked TIMESTAMP,
    status TEXT DEFAULT 'watching' CHECK(status IN ('watching', 'completed', 'dropped')),
    UNIQUE(title_id)
);

CREATE TABLE recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_title_id INTEGER REFERENCES titles(id),
    recommended_tmdb_id INTEGER NOT NULL,
    recommended_type TEXT NOT NULL,
    recommended_title TEXT,
    poster_path TEXT,
    tmdb_recommendation_score REAL,
    status TEXT DEFAULT 'unseen' CHECK(status IN ('unseen', 'dismissed', 'watched')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_title_id, recommended_tmdb_id)
);

CREATE TABLE streaming_availability (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tmdb_id INTEGER NOT NULL,
    tmdb_type TEXT NOT NULL,
    provider_name TEXT NOT NULL,
    provider_logo_path TEXT,
    monetization_type TEXT,              -- flatrate, rent, buy
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tmdb_id, tmdb_type, provider_name, monetization_type)
);

CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- Indexes
CREATE INDEX idx_watch_history_title ON watch_history(title_id);
CREATE INDEX idx_series_tracking_status ON series_tracking(status);
CREATE INDEX idx_recommendations_status ON recommendations(status);
CREATE INDEX idx_streaming_tmdb ON streaming_availability(tmdb_id, tmdb_type);
```

### 4. Recommendation Engine (`engine/recommendations.py`)

**Sources (TMDB endpoints):**

| Content Type | Endpoint | What It Returns |
|-------------|----------|-----------------|
| Movie recommendations | `/movie/{id}/recommendations` | Similar movies by user behavior |
| Movie sequels | `/collection/{id}` | All movies in a franchise |
| TV new seasons | `/tv/{id}` | Total season count |
| TV recommendations | `/tv/{id}/recommendations` | Similar shows |

**Logic:**
```
FOR each title in user's library WHERE tmdb_type = 'movie':
    1. GET /movie/{tmdb_id}/recommendations → store top 5
    2. IF movie belongs to collection → GET /collection/{id}
       → flag unwatched collection entries as "sequel/prequel"

FOR each series in series_tracking WHERE status = 'watching':
    1. GET /tv/{tmdb_id} → compare total_seasons vs max_watched_season
    2. IF total_seasons > max_watched_season → flag as "new season available"
    3. GET /tv/{tmdb_id}/recommendations → store top 3
```

### 5. Streaming Availability (`engine/availability.py`)

**Single endpoint per title:**
```
GET /movie/{id}/watch/providers  → filter by results.IL
GET /tv/{id}/watch/providers     → filter by results.IL
```

**Stored data:** provider name, logo, monetization type (flatrate/rent/buy)
**Update frequency:** daily cron
**Staleness accepted:** 24-32h (TMDB gets JustWatch data daily)

### 6. Daily Cron (`cron/daily_check.py`)

**Runs once per day. Orchestrates:**
```
1. For all series WHERE status = 'watching':
   → Check TMDB for new seasons
   → Update series_tracking.total_seasons_tmdb

2. For all titles:
   → Refresh streaming_availability from TMDB watch providers

3. For new recommendations found:
   → Insert into recommendations table

4. For any changes detected:
   → Send Telegram notification

5. Log results. If 3+ consecutive TMDB errors:
   → Send Telegram alert to admin
```

### 7. Dashboard (`dashboard/app.py`)

**Framework:** Flask or FastAPI with Jinja2 templates (server-rendered, no SPA)

**Three tabs:**

| Tab | Content | Data Source |
|-----|---------|-------------|
| Watch Next | Recommendations + unwatched sequels | `recommendations` table WHERE status = 'unseen' |
| Coming Soon | Series with announced but unreleased seasons | `series_tracking` WHERE upcoming season has future air date |
| My Library | All watched content | `titles` + `watch_history` joined |

**Each card shows:** Poster thumbnail, title (he/en), streaming providers (icons), action buttons

**Manual entry:** Search bar with TMDB autocomplete (debounce 300ms, min 3 chars, top 5 results with posters)

**Low-confidence review:** Banner at top: "X titles need your review" → list of `match_status = 'review'` entries with "correct" / "search again" options

### 8. Telegram Bot (`bot/telegram_notifier.py`)

**Push-only in v0.1. No commands. No browsing.**

**Notification types:**
```
🍿 New Season Alert
"Breaking Bad Season 6 is now available on Netflix!"
[Mark as watched] [Remind me later]

🎬 New Recommendation
"Based on Inception, you might like: Interstellar"
[Add to watchlist] [Dismiss]

❓ Title Disambiguation (low confidence)
"Which 'Crash' did you watch on 12/03/2024?"
[Crash (2004 Movie)] [Crash (2008 TV Series)]
→ 48h timeout → auto-pick highest TMDB popularity
```

**Implementation:** `python-telegram-bot` library with inline keyboards.

---

## Deployment Target (v0.1)

```
Single VPS (cheapest tier)
├── Python 3.11+
├── SQLite (file on disk)
├── Flask/FastAPI (port 8080)
├── Cron job (daily_check.py via system crontab)
└── Telegram bot (long-polling, not webhook)
```

No Docker. No reverse proxy. No SSL (optional, can add Caddy later). No CI/CD. Just `python app.py` and `crontab -e`.

---

## TMDB Attribution (Required)

Dashboard footer must include:
```
Powered by TMDB. This product uses the TMDB API but is not
endorsed or certified by TMDB.
[TMDB Logo]
```

---

*Architecture intentionally minimal. Add complexity only when v0.1 users demand it.*
