# Popcorn — Master Build Plan

> **Purpose:** Drive autonomous Claude Code build loop. CC reads this file each iteration, finds the first unchecked task `- [ ]`, executes it, verifies, commits+pushes, marks `- [x]`, repeats.
>
> **Resume:** On restart, scan for the first `- [ ]` checkbox — that's your next task. All prior `- [x]` tasks are done.
>
> **Abort:** If 3 consecutive tasks fail verification, STOP and add `## BUILD HALTED` section at bottom with error details. Wait for human review.

---

## Progress Tracker

| Phase | Name | Tasks | Status |
|-------|------|-------|--------|
| 0 | Infrastructure | 0.1–0.4 | Complete |
| 1 | Database | 1.1–1.2 | Complete |
| 2 | CSV Parser | 2.1–2.3 | Complete |
| 3 | TMDB API + Matcher | 3.1–3.3 | Complete |
| 4 | Engines | 4.1–4.6 | Complete |
| 5 | Dashboard | 5.1–5.10 | Complete |
| 6 | Telegram Bot | 6.1–6.3 | Complete |
| 7 | Cron + Docs | 7.1–7.4 | Not started |
| 8 | Integration Testing | 8.1–8.3 | Not started |
| 9 | Documentation + Polish | 9.1–9.4 | Not started |
| 10 | Definition of Done | 10.1–10.3 | Not started |

**Total: 45 tasks**

---

## Hard Constraints (MUST follow on every task)

1. **4 dependencies only:** `flask`, `requests`, `python-telegram-bot`, `python-dateutil`
2. **SQLite only, no ORM:** `import sqlite3`, parameterized queries with `?`
3. **TMDB sole data source:** all metadata from TMDB API v3
4. **Single-user:** no auth, no sessions, no multi-tenancy
5. **Server-rendered:** Flask + Jinja2 + Pico CSS. No React/Vue/npm/SPA
6. **No infrastructure:** no Docker, CI/CD, Redis, PostgreSQL
7. **TMDB rate limiting:** `time.sleep(0.2)` between EVERY TMDB API call
8. **BiDi:** `dir="auto"` on ALL text-displaying HTML elements
9. **TMDB attribution:** footer on every dashboard page
10. **Secrets in `.env`:** loaded via `config.py`, never hardcoded
11. **SQL safety:** ALWAYS parameterized queries with `?`. NEVER f-strings/format/concat in SQL
12. **Commit after each task:** `git add <files> && git commit -m "<message>" && git push`

---

## Authoritative Schema Column Names

Reference: `.claude/skills/schema-reference/references/schema.sql`

```
titles: id, tmdb_id, tmdb_type, title_en, title_he, poster_path, confidence, match_status, source, created_at
watch_history: id, title_id, raw_csv_title, watch_date, season_number, episode_name
series_tracking: id, title_id, tmdb_id, total_seasons_tmdb, max_watched_season, last_checked, status
recommendations: id, source_title_id, recommended_tmdb_id, recommended_type, recommended_title, poster_path, tmdb_recommendation_score, status, created_at
streaming_availability: id, tmdb_id, tmdb_type, provider_name, provider_logo_path, monetization_type, last_updated
settings: key, value
```

**Critical column names (not what you'd guess):**
- `series_tracking.total_seasons_tmdb` (not `total_seasons` or `seasons_count`)
- `series_tracking.max_watched_season` (not `last_watched_season`)
- `streaming_availability.provider_logo_path` (not `logo_path`)
- `recommendations.status` default = `'unseen'` (not `'active'` or `'new'`)
- `titles.match_status` values: `'auto'`, `'review'`, `'manual'`
- `series_tracking.status` values: `'watching'`, `'completed'`, `'dropped'`

---

## Phase 0: Infrastructure

### - [x] Task 0.1 — Create requirements.txt

**Files:** `requirements.txt`

**Description:**
Create `requirements.txt` with exactly 4 dependencies:
```
flask>=3.0
requests>=2.31
python-telegram-bot>=20.0
python-dateutil>=2.8
```

No other packages. No comments. No extras.

**Verification:**
```bash
python -c "lines = open('requirements.txt').read().strip().split('\n'); assert len(lines) == 4, f'Expected 4 deps, got {len(lines)}'; pkgs = [l.split('>=')[0] for l in lines]; assert sorted(pkgs) == ['flask', 'python-dateutil', 'python-telegram-bot', 'requests'], f'Wrong packages: {pkgs}'; print('OK: requirements.txt valid')"
```

**Commit:** `feat: add requirements.txt with 4 allowed dependencies`

---

### - [x] Task 0.2 — Create .env.example and .gitignore

**Files:** `.env.example`, `.gitignore`

**Description:**

`.env.example`:
```
TMDB_API_KEY=your_tmdb_api_key_here
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_ADMIN_CHAT_ID=your_chat_id_here
```

`.gitignore`:
```
.env
*.pyc
__pycache__/
popcorn.db
logs/*.log
*.csv
venv/
.venv/
```

**Verification:**
```bash
python -c "import os; assert os.path.isfile('.env.example'), '.env.example missing'; assert os.path.isfile('.gitignore'), '.gitignore missing'; gi = open('.gitignore').read(); assert '.env' in gi, '.env not in .gitignore'; assert 'popcorn.db' in gi, 'popcorn.db not in .gitignore'; print('OK: .env.example and .gitignore valid')"
```

**Commit:** `feat: add .env.example template and .gitignore`

---

### - [x] Task 0.3 — Create config.py

**Files:** `config.py`

**Description:**
Create `config.py` that loads `.env` manually (no python-dotenv — not in our 4 deps) and defines all constants.

```python
import os

# Load .env file manually
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.isfile(_env_path):
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, value = line.partition('=')
                os.environ.setdefault(key.strip(), value.strip())

# Base paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'popcorn.db')

# TMDB
TMDB_API_KEY = os.getenv('TMDB_API_KEY', '')
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_LANGUAGE_PRIMARY = "he-IL"
TMDB_LANGUAGE_FALLBACK = "en-US"
WATCH_REGION = "IL"
API_DELAY_SECONDS = 0.2

# Matching
MATCH_CONFIDENCE_THRESHOLD = 0.6

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_ADMIN_CHAT_ID = os.getenv('TELEGRAM_ADMIN_CHAT_ID', '')

# Disambiguation
DISAMBIGUATION_TIMEOUT_HOURS = 48
```

**Verification:**
```bash
python -c "import config; assert config.TMDB_BASE_URL == 'https://api.themoviedb.org/3'; assert config.TMDB_LANGUAGE_PRIMARY == 'he-IL'; assert config.MATCH_CONFIDENCE_THRESHOLD == 0.6; assert config.API_DELAY_SECONDS == 0.2; assert config.DISAMBIGUATION_TIMEOUT_HOURS == 48; assert 'popcorn.db' in config.DB_PATH; print('OK: config.py valid')"
```

**Commit:** `feat: add config.py with .env loader and all constants`

---

### - [x] Task 0.4 — Create directory structure and __init__.py files

**Files:** `db/.gitkeep`, `ingestion/__init__.py`, `engine/__init__.py`, `dashboard/__init__.py`, `dashboard/templates/.gitkeep`, `dashboard/static/.gitkeep`, `bot/__init__.py`, `cron/__init__.py`, `tests/__init__.py`, `tests/fixtures/.gitkeep`, `logs/.gitkeep`, `guides/.gitkeep`

**Description:**
Create all package directories with empty `__init__.py` files and `.gitkeep` for non-package dirs. Every `__init__.py` should be an empty file (zero bytes).

**Verification:**
```bash
python -c "import os; dirs = ['db', 'ingestion', 'engine', 'dashboard', 'dashboard/templates', 'dashboard/static', 'bot', 'cron', 'tests', 'tests/fixtures', 'logs', 'guides']; [None for d in dirs if not os.path.isdir(d) and (_ for _ in []).throw(AssertionError(f'{d} missing'))]; pkgs = ['ingestion', 'engine', 'dashboard', 'bot', 'cron', 'tests']; [None for p in pkgs if not os.path.isfile(os.path.join(p, '__init__.py')) and (_ for _ in []).throw(AssertionError(f'{p}/__init__.py missing'))]; print('OK: directory structure valid')"
```

**Commit:** `feat: create directory structure with __init__.py files`

---

## Phase 1: Database

### - [x] Task 1.1 — Create db/schema.sql

**Files:** `db/schema.sql`

**Description:**
Copy the authoritative schema from `.claude/skills/schema-reference/references/schema.sql` into `db/schema.sql`. The file must be identical — do NOT modify column names, types, constraints, or indexes.

6 tables: `titles`, `watch_history`, `series_tracking`, `recommendations`, `streaming_availability`, `settings`
4 indexes: `idx_watch_history_title`, `idx_series_tracking_status`, `idx_recommendations_status`, `idx_streaming_tmdb`
All tables use `CREATE TABLE IF NOT EXISTS`. All indexes use `CREATE INDEX IF NOT EXISTS`.

**Verification:**
```bash
python -c "import sqlite3; conn = sqlite3.connect(':memory:'); f = open('db/schema.sql'); conn.executescript(f.read()); f.close(); tables = [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]; expected = ['titles', 'watch_history', 'series_tracking', 'recommendations', 'streaming_availability', 'settings']; [None for t in expected if t not in tables and (_ for _ in []).throw(AssertionError(f'Table {t} missing'))]; cols = [r[1] for r in conn.execute('PRAGMA table_info(series_tracking)').fetchall()]; assert 'total_seasons_tmdb' in cols; assert 'max_watched_season' in cols; cols2 = [r[1] for r in conn.execute('PRAGMA table_info(streaming_availability)').fetchall()]; assert 'provider_logo_path' in cols2; conn.close(); print('OK: schema.sql valid with all 6 tables and correct columns')"
```

**Commit:** `feat: add db/schema.sql with 6 tables, indexes, and constraints`

---

### - [x] Task 1.2 — Create database initialization helper

**Files:** `db/__init__.py`, `db/init_db.py`

**Description:**
Create `db/__init__.py` (empty file) and `db/init_db.py` with functions to initialize the database and get connections:

```python
import os
import sqlite3


def get_connection(db_path=None):
    """Get a database connection with row_factory set."""
    if db_path is None:
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        from config import DB_PATH
        db_path = DB_PATH
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path=None):
    """Initialize database from schema.sql."""
    conn = get_connection(db_path)
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
    with open(schema_path) as f:
        conn.executescript(f.read())
    conn.close()


if __name__ == '__main__':
    init_db()
    print('Database initialized.')
```

**Verification:**
```bash
python -c "import sys; sys.path.insert(0, '.'); from db.init_db import get_connection, init_db; conn = get_connection(':memory:'); import os; schema_path = os.path.join('db', 'schema.sql'); f = open(schema_path); conn.executescript(f.read()); f.close(); tables = [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]; assert len(tables) == 6, f'Expected 6 tables, got {len(tables)}'; conn.close(); print('OK: db/init_db.py works correctly')"
```

**Commit:** `feat: add database initialization helper (db/init_db.py)`

---

## Phase 2: CSV Parser

### - [x] Task 2.1 — Create sample Netflix CSV fixture

**Files:** `tests/fixtures/sample_netflix.csv`

**Description:**
Create a sample Netflix CSV file for testing. Format: `Title,Date` (Netflix's actual format).

```csv
Title,Date
Breaking Bad: Season 1: Pilot,15/01/2023
Breaking Bad: Season 1: Cat's in the Bag...,16/01/2023
Breaking Bad: Season 2: Seven Thirty-Seven,20/02/2023
Inception,05/03/2022
Mission: Impossible - Fallout,25/12/2023
הכלה מאיסטנבול: עונה 1: פרק 3,10/05/2024
Bandersnatch,01/11/2020
Stranger Things: Season 3: Chapter One: Suzie Do You Copy?,14/07/2023
```

Note: Dates are DD/MM/YYYY (Israeli locale). `dayfirst=True` is essential.

**Verification:**
```bash
python -c "import csv; f = open('tests/fixtures/sample_netflix.csv', encoding='utf-8'); rows = list(csv.DictReader(f)); f.close(); assert len(rows) == 8, f'Expected 8 rows, got {len(rows)}'; assert 'Title' in rows[0], 'Missing Title column'; assert 'Date' in rows[0], 'Missing Date column'; assert 'Breaking Bad' in rows[0]['Title']; print('OK: sample_netflix.csv valid with 8 rows')"
```

**Commit:** `feat: add sample Netflix CSV fixture for testing`

---

### - [x] Task 2.2 — Implement csv_parser.py

**Files:** `ingestion/csv_parser.py`

**Description:**
Parse Netflix CSV into structured entries. Must handle:
- Colon-split heuristic: split on `: ` (colon + space)
- Season detection: `r'[Ss]eason\s+(\d+)'` or `r'עונה\s+(\d+)'`
- Date parsing with `dateutil.parser.parse(dayfirst=True)`
- Graceful skip of malformed rows with `logging.warning()`
- "Mission: Impossible" edge case — okay to misparse, TMDB corrects downstream

Function signature:
```python
def parse_netflix_csv(file_path: str) -> list[dict]:
```

Each returned dict has exactly these keys:
```python
{
    "title": str,           # Raw title from CSV (full string)
    "parsed_name": str,     # Extracted show/movie name (first segment)
    "season_number": int | None,
    "episode_name": str | None,
    "watch_date": str,      # ISO format YYYY-MM-DD
    "media_type_hint": str  # "tv" or "movie"
}
```

Rules:
- Split title on `: ` (colon-space)
- First segment = parsed_name
- Search remaining segments for season pattern: regex `r'[Ss]eason\s+(\d+)'` or `r'עונה\s+(\d+)'`
- If season found: media_type_hint = "tv", remaining non-season segments joined = episode_name
- If no season: media_type_hint = "movie", no episode
- Use `logging.warning()` on parse errors, skip row, continue
- Return empty list if file is empty or all rows fail

**Verification:**
```bash
python -c "import sys; sys.path.insert(0, '.'); from ingestion.csv_parser import parse_netflix_csv; entries = parse_netflix_csv('tests/fixtures/sample_netflix.csv'); assert len(entries) == 8, f'Expected 8 entries, got {len(entries)}'; bb = entries[0]; assert bb['parsed_name'] == 'Breaking Bad', f'Got: {bb[\"parsed_name\"]}'; assert bb['season_number'] == 1; assert bb['media_type_hint'] == 'tv'; inception = entries[3]; assert inception['parsed_name'] == 'Inception'; assert inception['season_number'] is None; assert inception['media_type_hint'] == 'movie'; hebrew = entries[5]; assert hebrew['season_number'] == 1; assert hebrew['media_type_hint'] == 'tv'; print('OK: csv_parser.py parses all 8 rows correctly')"
```

**Commit:** `feat: implement Netflix CSV parser with colon-split heuristic`

---

### - [x] Task 2.3 — Write csv_parser tests

**Files:** `tests/conftest.py`, `tests/test_csv_parser.py`

**Description:**
Create `tests/conftest.py` with shared fixtures:
```python
import os
import sys
import sqlite3
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

@pytest.fixture
def db_conn():
    """In-memory SQLite with schema applied."""
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    schema_path = os.path.join(os.path.dirname(__file__), '..', 'db', 'schema.sql')
    with open(schema_path) as f:
        conn.executescript(f.read())
    yield conn
    conn.close()

@pytest.fixture
def sample_csv_path():
    return os.path.join(os.path.dirname(__file__), 'fixtures', 'sample_netflix.csv')
```

Create `tests/test_csv_parser.py` with 6 test cases:
1. `test_parse_series_with_season` — "Breaking Bad: Season 1: Pilot" → name="Breaking Bad", season=1, episode="Pilot", type="tv"
2. `test_parse_movie` — "Inception" → name="Inception", season=None, episode=None, type="movie"
3. `test_parse_hebrew_title` — "הכלה מאיסטנבול: עונה 1: פרק 3" → season=1, type="tv"
4. `test_parse_date_dayfirst` — "15/01/2023" → "2023-01-15" (not "2023-15-01")
5. `test_skip_malformed_row` — empty title/date → skipped gracefully, no crash
6. `test_full_csv_parse` — parse sample_netflix.csv → returns 8 entries

All tests import from `ingestion.csv_parser`.

**Verification:**
```bash
python -m pytest tests/test_csv_parser.py -v
```

**Commit:** `test: add 6 csv_parser test cases`

---

## Phase 3: TMDB API + Matcher

### - [x] Task 3.1 — Create ingestion/tmdb_api.py (shared TMDB helper)

**Files:** `ingestion/tmdb_api.py`

**Description:**
Create the shared TMDB API helper module. ALL TMDB calls in the entire project go through these functions.

4 functions:
1. `tmdb_get(endpoint, params=None)` — core HTTP helper with `time.sleep(API_DELAY_SECONDS)` before every call
2. `search_tmdb(media_type, query, language)` — search for a title, returns first result or None
3. `two_pass_search(media_type, query)` — he-IL first, en-US fallback
4. `two_pass_search_with_type_fallback(query, preferred_type)` — full search strategy with type fallback, returns `(result, actual_type)` tuple

```python
import time
import logging
import requests
from config import TMDB_API_KEY, TMDB_BASE_URL, TMDB_LANGUAGE_PRIMARY, TMDB_LANGUAGE_FALLBACK, API_DELAY_SECONDS

logger = logging.getLogger(__name__)

def tmdb_get(endpoint: str, params: dict = None) -> dict | None:
    time.sleep(API_DELAY_SECONDS)
    url = f"{TMDB_BASE_URL}{endpoint}"
    params = params or {}
    params["api_key"] = TMDB_API_KEY
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"TMDB API error: {endpoint} - {e}")
        return None

def search_tmdb(media_type: str, query: str, language: str) -> dict | None:
    data = tmdb_get(f"/search/{media_type}", {"query": query, "language": language})
    if data and data.get("results"):
        return data["results"][0]
    return None

def two_pass_search(media_type: str, query: str) -> dict | None:
    result = search_tmdb(media_type, query, TMDB_LANGUAGE_PRIMARY)
    if not result:
        result = search_tmdb(media_type, query, TMDB_LANGUAGE_FALLBACK)
    return result

def two_pass_search_with_type_fallback(query: str, preferred_type: str) -> tuple[dict | None, str]:
    fallback_type = "movie" if preferred_type == "tv" else "tv"
    result = two_pass_search(preferred_type, query)
    if result:
        return result, preferred_type
    result = two_pass_search(fallback_type, query)
    if result:
        return result, fallback_type
    return None, preferred_type
```

**Verification:**
```bash
python -c "import sys; sys.path.insert(0, '.'); from ingestion.tmdb_api import tmdb_get, search_tmdb, two_pass_search, two_pass_search_with_type_fallback; assert callable(tmdb_get); assert callable(search_tmdb); assert callable(two_pass_search); assert callable(two_pass_search_with_type_fallback); print('OK: tmdb_api.py has all 4 functions')"
```

**Commit:** `feat: add shared TMDB API helper (ingestion/tmdb_api.py)`

---

### - [x] Task 3.2 — Implement tmdb_matcher.py

**Files:** `ingestion/tmdb_matcher.py`

**Description:**
TMDB matcher: takes parsed CSV entries, matches to TMDB, stores in DB.

Key functions:
```python
def calculate_confidence(query: str, result: dict) -> float:
    """Score 0.0-1.0: name similarity (70%) + popularity (30%, capped at 100)."""

def match_entries(entries: list[dict], conn) -> dict:
    """Match parsed entries to TMDB. Returns stats dict {matched, review, errors}."""
```

`calculate_confidence` uses `difflib.SequenceMatcher`:
```python
from difflib import SequenceMatcher
name_ratio = SequenceMatcher(None, query.lower(), result_title.lower()).ratio()
popularity_factor = min(result.get("popularity", 0) / 100, 1.0)
confidence = (name_ratio * 0.7) + (popularity_factor * 0.3)
```

`match_entries` flow:
1. Deduplicate entries by `parsed_name` (case-insensitive)
2. For each unique name: call `two_pass_search_with_type_fallback(parsed_name, media_type_hint)`
3. Calculate confidence, set `match_status = 'auto'` if >= 0.6, else `'review'`
4. Upsert into `titles` table: tmdb_id, tmdb_type, title_en (from `title` for movies or `name` for TV), title_he, poster_path, confidence, match_status, source='csv'
5. For ALL entries: get title_id from `titles`, insert into `watch_history`: title_id, raw_csv_title, watch_date, season_number, episode_name
6. For TV shows: upsert `series_tracking`: title_id, tmdb_id, total_seasons_tmdb (from TMDB `number_of_seasons` if available), max_watched_season (max season from entries), status='watching'
7. `conn.commit()` once at end

Imports: `from ingestion.tmdb_api import two_pass_search_with_type_fallback, tmdb_get`

TMDB movie results have `title` field, TV results have `name` field — handle both.

**Verification:**
```bash
python -c "import sys; sys.path.insert(0, '.'); from ingestion.tmdb_matcher import calculate_confidence, match_entries; score = calculate_confidence('Breaking Bad', {'title': 'Breaking Bad', 'name': 'Breaking Bad', 'popularity': 80}); assert 0.0 <= score <= 1.0, f'Score out of range: {score}'; assert score > 0.6, f'Expected high confidence, got {score}'; print(f'OK: tmdb_matcher.py works, sample confidence={score:.2f}')"
```

**Commit:** `feat: implement TMDB matcher with confidence scoring and dedup`

---

### - [x] Task 3.3 — Write TMDB matcher tests

**Files:** `tests/test_tmdb_matcher.py`

**Description:**
8 test cases, all with mocked TMDB API (no real calls). Use `unittest.mock.patch` on `ingestion.tmdb_api.tmdb_get` or `ingestion.tmdb_matcher.two_pass_search_with_type_fallback`. Mock `time.sleep` to avoid delays.

Test cases:
1. `test_high_confidence_match` — exact title match with high popularity → confidence > 0.6, status='auto'
2. `test_low_confidence_match` — fuzzy title with low popularity → confidence < 0.6, status='review'
3. `test_no_results` — TMDB returns nothing → status='review'
4. `test_type_fallback_tv_to_movie` — hint="tv" but only movie found → tmdb_type="movie"
5. `test_hebrew_title_match` — Hebrew title matched via he-IL → correct tmdb_id
6. `test_english_fallback` — he-IL returns nothing, en-US succeeds
7. `test_deduplication` — 5 entries with same parsed_name → only 1 TMDB search call
8. `test_batch_db_insert` — after matching, titles and watch_history rows exist in DB

All tests use the `db_conn` fixture from conftest.py for in-memory DB.

**Verification:**
```bash
python -m pytest tests/test_tmdb_matcher.py -v
```

**Commit:** `test: add 8 tmdb_matcher test cases with mocked TMDB API`

---

## Phase 4: Engines

### - [x] Task 4.1 — Implement engine/recommendations.py

**Files:** `engine/recommendations.py`

**Description:**
Generate recommendations from TMDB for titles in the database.

```python
import logging
from ingestion.tmdb_api import tmdb_get

logger = logging.getLogger(__name__)

def generate_recommendations(conn, tmdb_id: int, tmdb_type: str, source_title_id: int) -> int:
    """Generate recommendations for one title. Returns count of new recs added."""

def generate_all_recommendations(conn) -> dict:
    """Generate recommendations for all titles. Returns stats dict."""
```

`generate_recommendations` logic:
1. Call `tmdb_get(f"/{tmdb_type}/{tmdb_id}/recommendations", {"language": "he-IL"})`
2. Take top 5 results for movies, top 3 for TV
3. For each recommendation:
   - Skip if `recommended_tmdb_id` already watched (check via `SELECT t.tmdb_id FROM titles t JOIN watch_history wh ON t.id = wh.title_id WHERE t.tmdb_id = ?`)
   - Upsert into `recommendations`: source_title_id, recommended_tmdb_id, recommended_type (media_type), recommended_title (`title` for movies / `name` for TV), poster_path, tmdb_recommendation_score (`vote_average`), status='unseen'
4. For movies: check `belongs_to_collection` via `tmdb_get(f"/movie/{tmdb_id}", {"language": "he-IL"})` — if present, fetch collection parts and add unwatched ones as recs
5. `conn.commit()` after all recs for this title

`generate_all_recommendations` iterates all titles, calls `generate_recommendations` for each.

**Verification:**
```bash
python -c "import sys; sys.path.insert(0, '.'); from engine.recommendations import generate_recommendations, generate_all_recommendations; assert callable(generate_recommendations); assert callable(generate_all_recommendations); print('OK: recommendations.py has required functions')"
```

**Commit:** `feat: implement recommendation engine with collection detection`

---

### - [x] Task 4.2 — Implement engine/new_season_checker.py

**Files:** `engine/new_season_checker.py`

**Description:**
Detect new seasons for tracked TV series.

```python
import logging
from ingestion.tmdb_api import tmdb_get

logger = logging.getLogger(__name__)

def check_new_seasons(conn) -> list[dict]:
    """Check all watching series for new seasons. Returns list of alert dicts."""
```

Logic:
1. Query `SELECT st.*, t.tmdb_id, t.title_en, t.title_he FROM series_tracking st JOIN titles t ON st.title_id = t.id WHERE st.status = 'watching'`
2. For each series:
   - Call `tmdb_get(f"/tv/{tmdb_id}", {"language": "he-IL"})`
   - Compare response `number_of_seasons` with stored `total_seasons_tmdb`
   - If TMDB has more seasons: update `total_seasons_tmdb` and `last_checked`, check if `number_of_seasons > max_watched_season` → add to alerts
   - If same: just update `last_checked`
3. `conn.commit()` after all checks
4. Return list of alert dicts: `{"title_id", "tmdb_id", "title_en", "title_he", "new_season_number", "total_seasons"}`

**Verification:**
```bash
python -c "import sys; sys.path.insert(0, '.'); from engine.new_season_checker import check_new_seasons; assert callable(check_new_seasons); print('OK: new_season_checker.py has check_new_seasons')"
```

**Commit:** `feat: implement new season checker for tracked series`

---

### - [x] Task 4.3 — Implement engine/availability.py

**Files:** `engine/availability.py`

**Description:**
Fetch streaming availability for IL region from TMDB.

```python
import logging
from ingestion.tmdb_api import tmdb_get

logger = logging.getLogger(__name__)

def update_availability(conn, tmdb_id: int, tmdb_type: str) -> int:
    """Update streaming availability for one title. Returns provider count."""

def update_all_availability(conn) -> dict:
    """Update availability for all titles. Returns stats dict."""
```

`update_availability` logic:
1. Call `tmdb_get(f"/{tmdb_type}/{tmdb_id}/watch/providers")`
2. Extract IL data: `response["results"].get("IL", {})`
3. DELETE existing: `DELETE FROM streaming_availability WHERE tmdb_id = ? AND tmdb_type = ?`
4. For each monetization type (`flatrate`, `rent`, `buy`):
   - For each provider: INSERT into `streaming_availability` with tmdb_id, tmdb_type, provider_name (`provider_name`), provider_logo_path (`logo_path`), monetization_type
5. Return count of providers inserted

`update_all_availability` iterates all titles, calls `update_availability` for each.

**Verification:**
```bash
python -c "import sys; sys.path.insert(0, '.'); from engine.availability import update_availability, update_all_availability; assert callable(update_availability); assert callable(update_all_availability); print('OK: availability.py has required functions')"
```

**Commit:** `feat: implement streaming availability checker for IL region`

---

### - [x] Task 4.4 — Write recommendation engine tests

**Files:** `tests/test_recommendations.py`

**Description:**
6 test cases with mocked TMDB API (`@patch('ingestion.tmdb_api.tmdb_get')`) and in-memory DB (`db_conn` fixture). Mock `time.sleep`.

1. `test_movie_recommendations` — mock TMDB returning 7 results → only 5 stored (cap)
2. `test_tv_recommendations` — mock TMDB returning 5 results → only 3 stored (cap)
3. `test_skip_already_watched` — rec matches a title in watch_history → skipped
4. `test_collection_detection` — movie with belongs_to_collection → collection parts added as recs
5. `test_recommendation_caps` — verify exactly 5 movie / 3 TV cap
6. `test_empty_recommendations` — TMDB returns empty results → no crash, 0 recs

All tests pre-insert test data into `titles` and `watch_history` as needed.

**Verification:**
```bash
python -m pytest tests/test_recommendations.py -v
```

**Commit:** `test: add 6 recommendation engine test cases`

---

### - [x] Task 4.5 — Write new_season_checker tests

**Files:** `tests/test_new_season_checker.py`

**Description:**
4 test cases with mocked `tmdb_get` and `db_conn` fixture:

1. `test_new_season_detected` — TMDB shows more seasons than stored → alert returned, DB updated
2. `test_no_new_season` — same season count → no alert, last_checked updated
3. `test_skip_completed_series` — series with status='completed' → not checked
4. `test_skip_dropped_series` — series with status='dropped' → not checked

Pre-insert test data into `titles` + `series_tracking`.

**Verification:**
```bash
python -m pytest tests/test_new_season_checker.py -v
```

**Commit:** `test: add 4 new_season_checker test cases`

---

### - [x] Task 4.6 — Write availability tests

**Files:** `tests/test_availability.py`

**Description:**
4 test cases with mocked `tmdb_get` and `db_conn` fixture:

1. `test_update_availability_flatrate` — TMDB returns IL flatrate providers → stored correctly
2. `test_update_availability_multiple_types` — flatrate + rent + buy → all stored
3. `test_no_il_providers` — TMDB returns data but no IL region → 0 providers stored
4. `test_full_replace` — pre-existing providers deleted before new ones inserted

**Verification:**
```bash
python -m pytest tests/test_availability.py -v
```

**Commit:** `test: add 4 availability engine test cases`

---

## Phase 5: Dashboard

### - [x] Task 5.1 — Create base.html template

**Files:** `dashboard/templates/base.html`

**Description:**
Base Jinja2 template with:
- `<html dir="auto" lang="he">`
- Pico CSS via CDN: `<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">`
- Custom styles link: `<link rel="stylesheet" href="/static/style.css">`
- `<nav>` with 3 tabs: Watch Next (`/watch-next`), Coming Soon (`/coming-soon`), Library (`/library`)
- Active tab highlighted via `active_tab` template variable
- Upload form (POST `/upload`, file input for CSV, enctype="multipart/form-data")
- Review link shown when `review_count > 0`
- Flash messages block
- Footer with TMDB attribution: logo image + "This product uses the TMDB API but is not endorsed or certified by TMDB."
- TMDB logo URL: `https://www.themoviedb.org/assets/2/v4/logos/v2/blue_short-8e7b30f73a4020692ccca9c88bafe5dcb6f8a62a4c6bc55cd9ba82bb2cd95f6c.svg`
- `{% block content %}{% endblock %}`
- `dir="auto"` on ALL text-displaying elements

**Verification:**
```bash
python -c "content = open('dashboard/templates/base.html', encoding='utf-8').read(); assert 'pico' in content.lower(), 'Missing Pico CSS'; assert 'dir=\"auto\"' in content, 'Missing dir=auto'; assert 'themoviedb' in content, 'Missing TMDB attribution'; assert 'watch-next' in content, 'Missing watch-next tab'; assert 'coming-soon' in content, 'Missing coming-soon tab'; assert 'library' in content, 'Missing library tab'; assert '{% block content %}' in content, 'Missing content block'; print('OK: base.html has all required elements')"
```

**Commit:** `feat: add base.html template with Pico CSS, tabs, TMDB footer`

---

### - [x] Task 5.2 — Create watch_next.html template

**Files:** `dashboard/templates/watch_next.html`

**Description:**
Extends `base.html`. Displays recommendation cards.

- `{% extends "base.html" %}` with `{% set active_tab = "watch-next" %}`
- Loop over `recommendations` list
- Each card: poster image (`https://image.tmdb.org/t/p/w200` + poster_path), recommended title (`dir="auto"`), source title ("Because you watched X"), dismiss button (form POST to `/dismiss/{{ rec.id }}`)
- Streaming provider icons if available
- Empty state: "No recommendations yet. Upload your Netflix history to get started!"
- `dir="auto"` on all text elements

**Verification:**
```bash
python -c "content = open('dashboard/templates/watch_next.html', encoding='utf-8').read(); assert 'extends' in content and 'base.html' in content; assert 'recommendations' in content; assert 'dismiss' in content; assert 'dir=\"auto\"' in content; print('OK: watch_next.html valid')"
```

**Commit:** `feat: add watch_next.html recommendation cards template`

---

### - [x] Task 5.3 — Create coming_soon.html template

**Files:** `dashboard/templates/coming_soon.html`

**Description:**
Extends `base.html`. Shows series with new season alerts.

- `{% set active_tab = "coming-soon" %}`
- Loop over `alerts` list
- Each item: poster, series title (`dir="auto"`), "Season X now available!" badge
- Streaming provider icons if available
- Empty state: "All caught up! No new seasons detected."
- `dir="auto"` on all text elements

**Verification:**
```bash
python -c "content = open('dashboard/templates/coming_soon.html', encoding='utf-8').read(); assert 'extends' in content and 'base.html' in content; assert 'dir=\"auto\"' in content; print('OK: coming_soon.html valid')"
```

**Commit:** `feat: add coming_soon.html new seasons template`

---

### - [x] Task 5.4 — Create library.html template

**Files:** `dashboard/templates/library.html`

**Description:**
Extends `base.html`. Shows full watch history.

- `{% set active_tab = "library" %}`
- Loop over `titles` list (all matched titles with watch counts)
- Each item: poster, title (`dir="auto"`), type badge (movie/TV), watch count, last watched date
- Manual add section: text input with class `autocomplete-input`, hidden fields for tmdb_id/tmdb_type, submit button (POST `/add`)
- Empty state: "Your library is empty. Upload your Netflix viewing history to get started!"
- `dir="auto"` on all text elements

**Verification:**
```bash
python -c "content = open('dashboard/templates/library.html', encoding='utf-8').read(); assert 'extends' in content and 'base.html' in content; assert 'dir=\"auto\"' in content; print('OK: library.html valid')"
```

**Commit:** `feat: add library.html watch history template`

---

### - [x] Task 5.5 — Create review.html template

**Files:** `dashboard/templates/review.html`

**Description:**
Extends `base.html`. Shows low-confidence matches for manual review.

- NOT a tab — linked from nav when review_count > 0
- Loop over `review_items` list (titles with match_status='review')
- Each item: raw CSV title, current TMDB guess (poster + title), confidence score
- Resolve form: search input (class `autocomplete-input`), hidden fields, submit to POST `/resolve/{{ item.id }}`
- Accept button: confirms current guess (POST `/resolve/{{ item.id }}` with current tmdb_id)
- Empty state: "All titles matched! Nothing to review."
- `dir="auto"` on all text elements

**Verification:**
```bash
python -c "content = open('dashboard/templates/review.html', encoding='utf-8').read(); assert 'extends' in content and 'base.html' in content; assert 'resolve' in content; assert 'dir=\"auto\"' in content; print('OK: review.html valid')"
```

**Commit:** `feat: add review.html low-confidence match review template`

---

### - [x] Task 5.6 — Create dashboard/static/style.css

**Files:** `dashboard/static/style.css`

**Description:**
Minimal custom CSS. Pico CSS handles most styling. Only add:
- Card grid for recommendations/library (CSS grid or flexbox)
- Poster image sizing (max-width ~200px, aspect ratio preservation)
- Active tab indicator
- Dismiss button styling
- Provider icon sizing (small, inline, ~24px)
- Autocomplete dropdown positioning (absolute, z-index)
- Badge styling for movie/TV type indicators
- Minor responsive tweaks

Keep under 150 lines. Pico does the heavy lifting.

**Verification:**
```bash
python -c "content = open('dashboard/static/style.css').read(); assert len(content) > 50, 'style.css too short'; lines = content.strip().split(chr(10)); assert len(lines) <= 200, f'style.css too long: {len(lines)} lines'; print(f'OK: style.css valid ({len(lines)} lines)')"
```

**Commit:** `feat: add minimal custom CSS for dashboard`

---

### - [x] Task 5.7 — Implement dashboard/app.py (GET routes)

**Files:** `dashboard/app.py`

**Description:**
Flask app with the first 5 GET routes. Entry point with sys.path fix.

```python
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from flask import Flask, render_template, redirect, url_for
import sqlite3
from config import DB_PATH

app = Flask(__name__)
```

Routes:
1. `GET /` → `redirect(url_for('watch_next'))`
2. `GET /watch-next` → query recommendations WHERE status='unseen' joined with titles for poster/name + streaming_availability. Render `watch_next.html` with `recommendations` list
3. `GET /coming-soon` → query series_tracking WHERE total_seasons_tmdb > max_watched_season AND status='watching', joined with titles. Render `coming_soon.html` with `alerts` list
4. `GET /library` → query titles joined with watch_history (count, max date). Render `library.html` with `titles` list
5. `GET /review` → query titles WHERE match_status='review'. Render `review.html` with `review_items` list

Each route:
- Opens DB connection: `conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row`
- Runs parameterized query
- Passes `review_count` to all templates (for nav badge)
- Closes connection

Add `if __name__ == '__main__': app.run(debug=True, port=5000)`

**Verification:**
```bash
python -c "import sys, os; sys.path.insert(0, '.'); sys.path.insert(0, 'dashboard'); os.environ.setdefault('TMDB_API_KEY', 'test'); from dashboard.app import app; rules = [r.rule for r in app.url_map.iter_rules()]; assert '/' in rules; assert '/watch-next' in rules; assert '/coming-soon' in rules; assert '/library' in rules; assert '/review' in rules; print(f'OK: app.py has all 5 GET routes')"
```

**Commit:** `feat: implement Flask dashboard with 5 GET routes`

---

### - [x] Task 5.8 — Add POST /upload route

**Files:** `dashboard/app.py` (modify)

**Description:**
Add CSV upload route to app.py.

Logic:
1. Check rate limit: query `settings` for key='last_upload_date'. If within 24h → flash error, redirect
2. Get uploaded file from `request.files['csv_file']`
3. Validate file extension is `.csv`
4. Save to temp path via `tempfile.NamedTemporaryFile`
5. Call `parse_netflix_csv(temp_path)` from `ingestion.csv_parser`
6. Call `match_entries(entries, conn)` from `ingestion.tmdb_matcher`
7. Delete temp CSV file (`os.unlink`)
8. Update `settings`: `INSERT OR REPLACE INTO settings (key, value) VALUES ('last_upload_date', ?)`
9. Flash success with stats
10. Redirect to `/library`

Add imports: `from flask import request, flash`, `from ingestion.csv_parser import parse_netflix_csv`, `from ingestion.tmdb_matcher import match_entries`, `import tempfile`

Add `app.secret_key = os.urandom(24)` for flash messages.

**Verification:**
```bash
python -c "import sys, os; sys.path.insert(0, '.'); sys.path.insert(0, 'dashboard'); os.environ.setdefault('TMDB_API_KEY', 'test'); from dashboard.app import app; rules = {r.rule: r.methods for r in app.url_map.iter_rules()}; assert '/upload' in rules, 'Missing /upload route'; assert 'POST' in rules['/upload'], '/upload should accept POST'; print('OK: /upload POST route exists')"
```

**Commit:** `feat: add CSV upload route with rate limiting`

---

### - [x] Task 5.9 — Add GET /search and POST /add routes

**Files:** `dashboard/app.py` (modify)

**Description:**

`GET /search?q=` — TMDB autocomplete:
1. Get `q` from `request.args`, require min 3 chars, else return empty JSON array
2. Call `tmdb_get("/search/multi", {"query": q, "language": "he-IL"})`
3. Return `jsonify(results)` — top 5 with: tmdb_id (`id`), media_type, title (use `title` for movies, `name` for TV), poster_path, year (extract from `release_date` or `first_air_date`)

`POST /add` — manual title add:
1. Get `tmdb_id`, `tmdb_type` from `request.form`
2. Fetch details: `tmdb_get(f"/{tmdb_type}/{tmdb_id}", {"language": "he-IL"})`
3. INSERT into `titles`: tmdb_id, tmdb_type, title_en, poster_path, match_status='manual', source='manual', confidence=1.0
4. If tmdb_type == 'tv': INSERT into `series_tracking`
5. Flash success, redirect to `/library`

Add imports: `from flask import jsonify`, `from ingestion.tmdb_api import tmdb_get`

**Verification:**
```bash
python -c "import sys, os; sys.path.insert(0, '.'); sys.path.insert(0, 'dashboard'); os.environ.setdefault('TMDB_API_KEY', 'test'); from dashboard.app import app; rules = {r.rule: r.methods for r in app.url_map.iter_rules()}; assert '/search' in rules; assert '/add' in rules; assert 'POST' in rules['/add']; print('OK: /search and /add routes exist')"
```

**Commit:** `feat: add search autocomplete and manual add routes`

---

### - [x] Task 5.10 — Add POST /resolve, POST /dismiss routes + autocomplete JS

**Files:** `dashboard/app.py` (modify), `dashboard/templates/base.html` (modify)

**Description:**

`POST /resolve/<int:title_id>`:
1. Get `new_tmdb_id` and `new_tmdb_type` from form (if user picked different match)
2. If provided: UPDATE titles SET tmdb_id=?, tmdb_type=?, match_status='manual', confidence=1.0 WHERE id=?
3. If not provided (accept current): UPDATE titles SET match_status='auto' WHERE id=?
4. Redirect to `/review`

`POST /dismiss/<int:rec_id>`:
1. UPDATE recommendations SET status='dismissed' WHERE id=?
2. Redirect to `/watch-next`

Autocomplete JS in `base.html` (inside `{% block scripts %}` or before `</body>`):
- Attach to inputs with class `autocomplete-input`
- 300ms debounce on `input` event
- Min 3 characters
- Fetch `/search?q=...`
- Display dropdown with poster thumbnail + title + year + type badge
- On select: populate hidden form fields (tmdb_id, tmdb_type)

**Verification:**
```bash
python -c "import sys, os; sys.path.insert(0, '.'); sys.path.insert(0, 'dashboard'); os.environ.setdefault('TMDB_API_KEY', 'test'); from dashboard.app import app; rules = {r.rule: r.methods for r in app.url_map.iter_rules()}; resolve_found = any('resolve' in r for r in rules); dismiss_found = any('dismiss' in r for r in rules); assert resolve_found, 'Missing /resolve route'; assert dismiss_found, 'Missing /dismiss route'; print('OK: all 10 routes implemented')"
```

**Commit:** `feat: add resolve, dismiss routes and autocomplete JS — dashboard complete`

---

## Phase 6: Telegram Bot

### - [x] Task 6.1 — Implement bot/telegram_notifier.py

**Files:** `bot/telegram_notifier.py`

**Description:**
Telegram bot with 4 async send functions + callback handler + polling setup. Push-only megaphone — NO /commands.

```python
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import logging
import sqlite3
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_CHAT_ID, DB_PATH

logger = logging.getLogger(__name__)
```

4 async send functions:
```python
async def send_new_season_alert(chat_id, title, season_number, poster_path=None):
    """Send new season notification with watched/remind inline keyboard."""
    # Callback data: watched_{tmdb_id}, remind_{tmdb_id}

async def send_recommendation(chat_id, source_title, rec_titles):
    """Send recommendation notification."""

async def send_disambiguation(chat_id, title_id, raw_title, candidates):
    """Send disambiguation with top 3 candidates as inline keyboard."""
    # Callback data: disambig_{title_id}_{tmdb_id}

async def send_admin_alert(message):
    """Send error alert to TELEGRAM_ADMIN_CHAT_ID."""
```

Callback handler:
```python
async def handle_callback(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith('watched_'): ...
    elif data.startswith('remind_'): ...
    elif data.startswith('disambig_'): ...
```

Polling setup:
```python
def run_bot():
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("No TELEGRAM_BOT_TOKEN set, bot not starting")
        return
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.run_polling()
```

Guard bot creation: `bot = Bot(token=TELEGRAM_BOT_TOKEN) if TELEGRAM_BOT_TOKEN else None`

**Verification:**
```bash
python -c "import sys; sys.path.insert(0, '.'); from bot.telegram_notifier import send_new_season_alert, send_recommendation, send_disambiguation, send_admin_alert, handle_callback, run_bot; import asyncio; assert asyncio.iscoroutinefunction(send_new_season_alert); assert asyncio.iscoroutinefunction(send_recommendation); assert asyncio.iscoroutinefunction(send_disambiguation); assert asyncio.iscoroutinefunction(send_admin_alert); assert asyncio.iscoroutinefunction(handle_callback); assert callable(run_bot); print('OK: telegram_notifier.py has 4 async send functions + callback + run_bot')"
```

**Commit:** `feat: implement Telegram bot with async send functions and callback handler`

---

### - [x] Task 6.2 — Write Telegram bot tests

**Files:** `tests/test_telegram.py`

**Description:**
4 test cases with mocked Bot. Mock `telegram.Bot` to prevent real API calls.

1. `test_send_new_season_alert` — mock Bot.send_message → called with correct text and inline keyboard
2. `test_send_disambiguation` — mock Bot.send_message → 3 candidates → 3 inline buttons
3. `test_send_admin_alert` — mock Bot.send_message → called with ADMIN_CHAT_ID
4. `test_callback_handler_disambig` — mock callback update with disambig data → titles table updated

Use `asyncio.get_event_loop().run_until_complete()` or `loop.run_until_complete()` to test async functions (no extra deps).

**Verification:**
```bash
python -m pytest tests/test_telegram.py -v
```

**Commit:** `test: add 4 Telegram bot test cases`

---

### - [x] Task 6.3 — Verify bot module completeness

**Files:** None (verification only, fix if needed)

**Description:**
Verify the bot module is complete — all functions exist, imports work, callback data formats match the spec.

Callback data formats must be:
- `watched_{tmdb_id}`
- `remind_{tmdb_id}`
- `disambig_{title_id}_{tmdb_id}`

**Verification:**
```bash
python -c "import sys; sys.path.insert(0, '.'); from bot.telegram_notifier import send_new_season_alert, send_recommendation, send_disambiguation, send_admin_alert, handle_callback, run_bot; print('OK: bot module complete')"
```

**Commit:** `chore: verify bot module completeness` (only if fixes needed)

---

## Phase 7: Cron + Docs

### - [x] Task 7.1 — Implement cron/daily_check.py

**Files:** `cron/daily_check.py`

**Description:**
Daily orchestration script. 5 phases, sequential, with logging.

```python
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import logging
import asyncio
from datetime import datetime, timedelta
import sqlite3
from config import DB_PATH, TELEGRAM_ADMIN_CHAT_ID, DISAMBIGUATION_TIMEOUT_HOURS
```

5 phases (run in exact order):
1. **Check new seasons** — `from engine.new_season_checker import check_new_seasons` → for each alert: `asyncio.run(send_new_season_alert(TELEGRAM_ADMIN_CHAT_ID, ...))`
2. **Refresh streaming availability** — `from engine.availability import update_all_availability`
3. **Generate recommendations (Monday only)** — if `datetime.today().weekday() == 0`: `from engine.recommendations import generate_all_recommendations`, else log "Skipping recommendations — not Monday"
4. **Timeout stale disambiguations** — query `titles WHERE match_status='review' AND created_at < ?` (now - 48h), set match_status='auto' for stale ones
5. **Error check** — track consecutive TMDB errors across phases, if >= 3: `asyncio.run(send_admin_alert(...))`

Requirements:
- Log to both stdout and `logs/cron.log` using `logging.basicConfig` with `StreamHandler` + `FileHandler`
- Log phase name, start time, end time, duration, items processed
- Continue to next phase even if current phase errors (try/except per phase, log traceback)
- Entry point: `if __name__ == '__main__': daily_check()`

```python
def daily_check():
    """Run all 5 daily check phases."""
```

**Verification:**
```bash
python -c "import sys; sys.path.insert(0, '.'); from cron.daily_check import daily_check; assert callable(daily_check); print('OK: daily_check.py has daily_check function')"
```

**Commit:** `feat: implement 5-phase daily cron orchestrator`

---

### - [x] Task 7.2 — Write daily_check tests

**Files:** `tests/test_daily_check.py`

**Description:**
4 test cases with mocked engines and bot:

1. `test_full_run_monday` — mock datetime.today().weekday() to return 0 (Monday), mock all engines + bot → recommendations generated
2. `test_full_run_non_monday` — mock weekday to return 1 (Tuesday) → recommendations skipped
3. `test_phase_error_continues` — mock one engine to raise Exception → next phase still runs
4. `test_disambiguation_timeout` — insert a review title with old created_at (> 48h) → auto-resolved after daily_check

Mock all engines (`check_new_seasons`, `update_all_availability`, `generate_all_recommendations`) and bot functions. Use `db_conn` fixture.

**Verification:**
```bash
python -m pytest tests/test_daily_check.py -v
```

**Commit:** `test: add 4 daily_check test cases`

---

### - [ ] Task 7.3 — Create Netflix export guide (English)

**Files:** `guides/netflix_export_guide_en.md`

**Description:**
Step-by-step guide for non-technical users to export Netflix viewing history.

Steps:
1. Open Netflix in a web browser (not the app)
2. Click your profile icon → Account
3. Scroll to Profile & Parental Controls
4. Click the profile you want to export
5. Click "Viewing Activity"
6. Scroll to the bottom of the page
7. Click "Download All"
8. Save the file (downloads as `NetflixViewingHistory.csv`)
9. Go to the Popcorn dashboard
10. Click "Upload" and select the CSV file
11. Wait for processing to complete
12. Review any flagged titles if needed

Simple language, no technical jargon.

**Verification:**
```bash
python -c "content = open('guides/netflix_export_guide_en.md', encoding='utf-8').read(); assert 'Netflix' in content; assert 'Download' in content or 'download' in content; assert 'CSV' in content or 'csv' in content; assert len(content) > 200; print('OK: English guide valid')"
```

**Commit:** `docs: add Netflix export guide (English)`

---

### - [ ] Task 7.4 — Create Netflix export guide (Hebrew)

**Files:** `guides/netflix_export_guide_he.md`

**Description:**
Same guide as English but in Hebrew. Same step count and flow.

**Verification:**
```bash
python -c "content = open('guides/netflix_export_guide_he.md', encoding='utf-8').read(); assert 'Netflix' in content or chr(1504) in content; assert len(content) > 200; has_hebrew = any(chr(0x0590) <= c <= chr(0x05FF) for c in content); assert has_hebrew, 'No Hebrew characters found'; print('OK: Hebrew guide valid')"
```

**Commit:** `docs: add Netflix export guide (Hebrew)`

---

## Phase 8: Integration Testing

### - [ ] Task 8.1 — Write dashboard integration tests

**Files:** `tests/test_dashboard.py`

**Description:**
Test Flask routes with test client and in-memory DB. Mock `DB_PATH` to use temp SQLite file (or patch `sqlite3.connect`).

6 test cases:
1. `test_root_redirects` — GET / → 302 redirect to /watch-next
2. `test_watch_next_empty` — GET /watch-next with empty DB → 200
3. `test_library_empty` — GET /library with empty DB → 200
4. `test_review_empty` — GET /review with empty DB → 200
5. `test_upload_rate_limit` — POST /upload twice quickly → second rejected
6. `test_dismiss_recommendation` — insert rec, POST /dismiss/{id} → status='dismissed'

Use `app.test_client()`. Initialize temp DB with schema before each test.

**Verification:**
```bash
python -m pytest tests/test_dashboard.py -v
```

**Commit:** `test: add 6 dashboard integration test cases`

---

### - [ ] Task 8.2 — Write end-to-end CSV import test

**Files:** `tests/test_integration.py`

**Description:**
Full pipeline test: CSV → parse → match → DB.

1. `test_csv_to_db_pipeline` — parse sample CSV, mock TMDB responses for all titles, call match_entries → verify:
   - Correct number of unique titles in `titles` table
   - All watch_history entries present
   - series_tracking entries for TV shows
   - Confidence scores calculated
   - Match statuses assigned ('auto' or 'review')

Uses `db_conn` fixture, mocked TMDB (`@patch('ingestion.tmdb_api.tmdb_get')`), sample CSV fixture.

**Verification:**
```bash
python -m pytest tests/test_integration.py -v
```

**Commit:** `test: add end-to-end CSV import integration test`

---

### - [ ] Task 8.3 — Run full test suite and fix failures

**Files:** Any files needing fixes

**Description:**
Run the complete test suite. Fix any failures. Re-run until all pass.

**Verification:**
```bash
python -m pytest tests/ -v --tb=short
```

**Commit:** `fix: resolve test suite failures (full green)` (only if fixes needed)

---

## Phase 9: Documentation + Polish

### - [ ] Task 9.1 — Create README.md

**Files:** `README.md`

**Description:**
Project README with:
- Project title and one-line description
- Features list
- Quick start (setup .env, install deps, init DB, run dashboard)
- Key commands (run dashboard, run tests, run cron)
- Tech stack
- TMDB attribution

Keep concise.

**Verification:**
```bash
python -c "content = open('README.md', encoding='utf-8').read(); assert 'Popcorn' in content; assert 'TMDB' in content; assert 'requirements' in content.lower(); assert len(content) > 300; print('OK: README.md valid')"
```

**Commit:** `docs: add README.md`

---

### - [ ] Task 9.2 — Create CHANGELOG.md

**Files:** `CHANGELOG.md`

**Description:**
Initial changelog:
```markdown
# Changelog

## v0.1.0 — Initial Release

- Netflix CSV import with automatic TMDB matching
- Two-pass language search (Hebrew then English)
- Recommendation engine with collection detection
- New season detection for tracked series
- Streaming availability for Israel region
- Flask dashboard with 3 tabs (Watch Next, Coming Soon, Library)
- Manual title entry via TMDB autocomplete
- Low-confidence match review workflow
- Telegram push notifications (new seasons, recommendations)
- Daily cron orchestration (5 phases)
- BiDi support for Hebrew/English content
- Netflix export guides (Hebrew + English)
```

**Verification:**
```bash
python -c "content = open('CHANGELOG.md', encoding='utf-8').read(); assert '0.1.0' in content; assert 'Netflix' in content; print('OK: CHANGELOG.md valid')"
```

**Commit:** `docs: add CHANGELOG.md with v0.1.0 entry`

---

### - [ ] Task 9.3 — Add logging configuration

**Files:** `config.py` (modify)

**Description:**
Add at the end of config.py:

```python
import logging

LOG_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)
```

**Verification:**
```bash
python -c "import sys; sys.path.insert(0, '.'); import config; import logging; logger = logging.getLogger('test'); logger.info('Test log message'); print('OK: logging configured')"
```

**Commit:** `feat: add logging configuration to config.py`

---

### - [ ] Task 9.4 — Final code quality pass

**Files:** Any files needing cleanup

**Description:**
Verify all modules import correctly. Fix any issues found.

**Verification:**
```bash
python -c "import sys, importlib; sys.path.insert(0, '.'); modules = ['ingestion.csv_parser', 'ingestion.tmdb_api', 'ingestion.tmdb_matcher', 'engine.recommendations', 'engine.new_season_checker', 'engine.availability', 'bot.telegram_notifier', 'cron.daily_check']; failed = []; [failed.append(f'{m}: {e}') for m in modules for e in [None] if not (lambda: (importlib.import_module(m), True))() or False]; ok = len(modules) - len(failed); print(f'OK: {ok}/{len(modules)} modules import successfully') if not failed else (print('FAILURES:'), [print(f'  {f}') for f in failed])"
```

Simpler alternative verification:
```bash
python -c "import sys; sys.path.insert(0, '.'); from ingestion.csv_parser import parse_netflix_csv; from ingestion.tmdb_api import tmdb_get; from ingestion.tmdb_matcher import match_entries; from engine.recommendations import generate_all_recommendations; from engine.new_season_checker import check_new_seasons; from engine.availability import update_all_availability; from bot.telegram_notifier import send_new_season_alert; from cron.daily_check import daily_check; print('OK: all 8 modules import successfully')"
```

**Commit:** `chore: code quality pass — fix imports and issues` (only if fixes needed)

---

## Phase 10: Definition of Done

### - [ ] Task 10.1 — Verify all tests pass

**Files:** None (verification only)

**Description:**
Run the complete test suite one final time.

**Verification:**
```bash
python -m pytest tests/ -v --tb=short
```

**Commit:** None (verification only — no commit unless fixes needed)

---

### - [ ] Task 10.2 — Verify dashboard starts

**Files:** None (verification only)

**Description:**
Verify the Flask dashboard starts and serves pages.

**Verification:**
```bash
python -c "import sys, os; sys.path.insert(0, '.'); os.environ['TMDB_API_KEY'] = 'test_key'; from db.init_db import init_db; from config import DB_PATH; init_db() if not os.path.exists(DB_PATH) else None; from dashboard.app import app; client = app.test_client(); resp = client.get('/'); assert resp.status_code in (302, 301), f'Expected redirect, got {resp.status_code}'; resp = client.get('/watch-next'); assert resp.status_code == 200; resp = client.get('/library'); assert resp.status_code == 200; print('OK: dashboard starts and serves all pages')"
```

**Commit:** None (verification only)

---

### - [ ] Task 10.3 — Final DoD checklist verification

**Files:** None (verification only)

**Description:**
Verify all files exist for v0.1 Definition of Done.

**Verification:**
```bash
python -c "import os; checks = {'CSV parser': os.path.isfile('ingestion/csv_parser.py'), 'TMDB matcher': os.path.isfile('ingestion/tmdb_matcher.py'), 'TMDB API helper': os.path.isfile('ingestion/tmdb_api.py'), 'Recommendations': os.path.isfile('engine/recommendations.py'), 'Season checker': os.path.isfile('engine/new_season_checker.py'), 'Availability': os.path.isfile('engine/availability.py'), 'Dashboard': os.path.isfile('dashboard/app.py'), 'Base template': os.path.isfile('dashboard/templates/base.html'), 'Watch Next template': os.path.isfile('dashboard/templates/watch_next.html'), 'Coming Soon template': os.path.isfile('dashboard/templates/coming_soon.html'), 'Library template': os.path.isfile('dashboard/templates/library.html'), 'Review template': os.path.isfile('dashboard/templates/review.html'), 'Telegram bot': os.path.isfile('bot/telegram_notifier.py'), 'Daily cron': os.path.isfile('cron/daily_check.py'), 'Guide EN': os.path.isfile('guides/netflix_export_guide_en.md'), 'Guide HE': os.path.isfile('guides/netflix_export_guide_he.md'), 'Schema': os.path.isfile('db/schema.sql'), 'Config': os.path.isfile('config.py'), 'README': os.path.isfile('README.md')}; passed = sum(1 for v in checks.values() if v); total = len(checks); [print(f'  {chr(9989) if ok else chr(10060)} {name}') for name, ok in checks.items()]; print(f'{chr(10)}{passed}/{total} checks passed'); assert passed == total, 'Not all checks passed!'; print(f'{chr(10)}BUILD COMPLETE — Popcorn v0.1 is ready!')"
```

**Commit:** `chore: verify v0.1 Definition of Done — all criteria met`

---

## Abort Conditions

If **3 consecutive tasks** fail verification:
1. **STOP** — do not attempt the next task
2. Add a section at the end of this file:
   ```
   ## BUILD HALTED
   **Failed tasks:** [list task numbers]
   **Error details:** [paste verification output]
   **Last successful task:** [task number]
   **Suggested fix:** [your analysis]
   ```
3. Commit and push the updated master-plan.md
4. Wait for human review

---

## Resume Instructions

When starting a new iteration:
1. Read this file (`master-plan.md`)
2. Find the first `- [ ]` checkbox (unchecked task)
3. Execute that task completely
4. Run the verification command — it MUST exit 0
5. If verification passes: commit, push, mark `- [x]`
6. If verification fails: attempt to fix (max 2 retries), then count as consecutive failure
7. Move to next task

**DO NOT** skip tasks. **DO NOT** reorder phases. **DO NOT** modify completed tasks.
