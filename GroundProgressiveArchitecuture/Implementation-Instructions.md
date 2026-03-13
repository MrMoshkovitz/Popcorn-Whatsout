# 🍿 Popcorn — Implementation Instructions

**Step-by-step build plan. Order matters. No skipping.**

---

## Pre-Flight Checklist

Before writing any code:

- [ ] Get TMDB API key: https://www.themoviedb.org/settings/api (free, instant)
- [ ] Create Telegram bot via @BotFather → save token
- [ ] Validate TMDB Israel coverage: query 20 popular titles with `watch_region=IL` — if <50% return providers, demote streaming feature to "best effort"
- [ ] Export your own Netflix CSV from https://www.netflix.com/viewingactivity → verify format is `Title,Date`
- [ ] Choose VPS or local machine for development

---

## Build Order (7 Steps)

### Step 1: Database Schema + Config

**Goal:** SQLite database exists, `.env` loaded, constants defined.

**Files:**
- `db/schema.sql` — create all tables (see Architecture doc)
- `config.py` — load `.env`, define constants:
  ```
  TMDB_API_KEY
  TMDB_BASE_URL = "https://api.themoviedb.org/3"
  TMDB_LANGUAGE_PRIMARY = "he-IL"
  TMDB_LANGUAGE_FALLBACK = "en-US"
  WATCH_REGION = "IL"
  TELEGRAM_BOT_TOKEN
  TELEGRAM_ADMIN_CHAT_ID
  MATCH_CONFIDENCE_THRESHOLD = 0.6
  API_DELAY_SECONDS = 0.2
  DISAMBIGUATION_TIMEOUT_HOURS = 48
  ```
- `.env.example` — template for secrets

**Acceptance test:** `python -c "import sqlite3; conn = sqlite3.connect('popcorn.db')"` succeeds. Config loads without errors.

**Time estimate:** 30 minutes.

---

### Step 2: CSV Parser

**Goal:** Parse Netflix CSV into structured entries.

**File:** `ingestion/csv_parser.py`

**Logic:**
1. Read CSV with `csv.DictReader`
2. For each row: split `Title` on `:`, extract show name / season / episode
3. Parse `Date` with `dateutil.parser.parse(dayfirst=True)`
4. Return list of `ParsedEntry` dicts

**Test file:** `tests/test_csv_parser.py`

**Test cases (minimum):**
```
"Breaking Bad: Season 1: Pilot","1/15/2023"
  → name="Breaking Bad", season=1, episode="Pilot", is_series=True

"Inception","3/5/2022"
  → name="Inception", season=None, episode=None, is_series=False

"Mission: Impossible - Fallout","12/25/2023"
  → name="Mission: Impossible - Fallout" (tricky: colon in movie name)
  → is_series=False (no season pattern after colon)

"הכלה מאיסטנבול: עונה 1: פרק 3","5/10/2024"
  → name="הכלה מאיסטנבול", season=1, is_series=True

"","" → skip gracefully

"Bandersnatch","11/1/2020"
  → name="Bandersnatch", is_series=False (no colon)
```

**Key decision:** The "Mission: Impossible" case will initially misparse. The TMDB matcher (Step 3) corrects this — if TMDB finds no TV show named "Mission", it falls back to movie search with the full title. Don't over-engineer the parser.

**Time estimate:** 1-2 hours.

---

### Step 3: TMDB Matcher

**Goal:** Take parsed entries, match each to a TMDB ID.

**File:** `ingestion/tmdb_matcher.py`

**Logic (per entry):**
```python
def match_entry(entry: ParsedEntry) -> MatchedTitle:
    if entry.is_likely_series:
        result = search_tmdb("tv", entry.parsed_name, "he-IL")
        if not result:
            result = search_tmdb("tv", entry.parsed_name, "en-US")
        if not result:
            result = search_tmdb("movie", entry.parsed_name, "he-IL")  # fallback
    else:
        result = search_tmdb("movie", entry.parsed_name, "he-IL")
        if not result:
            result = search_tmdb("movie", entry.parsed_name, "en-US")
        if not result:
            result = search_tmdb("tv", entry.parsed_name, "he-IL")  # fallback

    if result:
        confidence = calculate_confidence(entry.parsed_name, result)
        status = "auto" if confidence >= THRESHOLD else "review"
        return MatchedTitle(tmdb_id=result.id, ..., confidence=confidence, match_status=status)
    else:
        return MatchedTitle(match_status="review", ...)  # No match found
```

**Confidence calculation:**
```python
from difflib import SequenceMatcher

def calculate_confidence(query: str, tmdb_result) -> float:
    string_sim = SequenceMatcher(None, query.lower(), tmdb_result.title.lower()).ratio()
    # Normalize TMDB popularity to 0-1 range (cap at 100)
    popularity_factor = min(tmdb_result.popularity / 100, 1.0)
    return (string_sim * 0.7) + (popularity_factor * 0.3)
```

**Rate limiting:** `time.sleep(API_DELAY_SECONDS)` between each TMDB API call.

**Batch import flow:**
1. Parse all CSV entries
2. Deduplicate by `parsed_name` (same show appears many times for different episodes)
3. Match unique titles only → much fewer API calls than raw entry count
4. Store results in `titles` table (upsert)
5. Store individual watch events in `watch_history` table
6. For series: populate `series_tracking` with max watched season

**Test cases:**
- "Breaking Bad" → should match TMDB TV ID 1396
- "Inception" → should match TMDB Movie ID 27205
- "asdfghjkl" → should return match_status="review"
- Hebrew title "פאודה" → should match via he-IL search

**Time estimate:** 2-3 hours.

---

### Step 4: Recommendation + New Season Engine

**Goal:** Generate recommendations and detect new seasons.

**Files:**
- `engine/recommendations.py`
- `engine/new_season_checker.py`
- `engine/availability.py`

**Recommendations logic:**
```python
def generate_recommendations(title_id: int, tmdb_id: int, tmdb_type: str):
    # Get TMDB recommendations
    recs = tmdb_get(f"/{tmdb_type}/{tmdb_id}/recommendations")
    for rec in recs.results[:5]:  # Top 5 only
        upsert_recommendation(title_id, rec)

    # For movies: check if part of a collection
    if tmdb_type == "movie":
        details = tmdb_get(f"/movie/{tmdb_id}")
        if details.belongs_to_collection:
            collection = tmdb_get(f"/collection/{details.belongs_to_collection.id}")
            for part in collection.parts:
                if part.id != tmdb_id:  # Not the same movie
                    upsert_recommendation(title_id, part, label="sequel/prequel")
```

**New season checker logic:**
```python
def check_new_seasons():
    tracking = db.query("SELECT * FROM series_tracking WHERE status = 'watching'")
    alerts = []
    for series in tracking:
        tv_details = tmdb_get(f"/tv/{series.tmdb_id}")
        if tv_details.number_of_seasons > series.total_seasons_tmdb:
            db.update_total_seasons(series.id, tv_details.number_of_seasons)
            if tv_details.number_of_seasons > series.max_watched_season:
                alerts.append(series)
    return alerts
```

**Availability logic:**
```python
def update_availability(tmdb_id: int, tmdb_type: str):
    providers = tmdb_get(f"/{tmdb_type}/{tmdb_id}/watch/providers")
    il_data = providers.results.get("IL", {})
    # Clear old data for this title
    db.delete_availability(tmdb_id, tmdb_type)
    for monetization_type in ["flatrate", "rent", "buy"]:
        for provider in il_data.get(monetization_type, []):
            db.insert_availability(tmdb_id, tmdb_type, provider, monetization_type)
```

**Time estimate:** 3-4 hours.

---

### Step 5: Dashboard

**Goal:** Three-tab web UI with manual entry.

**File:** `dashboard/app.py` + Jinja2 templates

**Tech:** Flask (simpler than FastAPI for server-rendered HTML). Single file is fine.

**Routes:**
```
GET  /                          → redirect to /watch-next
GET  /watch-next                → recommendations tab
GET  /coming-soon               → new seasons / unreleased content
GET  /library                   → full watch history
GET  /review                    → low-confidence matches needing review
POST /upload                    → CSV upload + process
GET  /search?q=                 → TMDB autocomplete (JSON, for manual entry)
POST /add                       → manual title add
POST /resolve/{title_id}        → confirm/change TMDB match
POST /dismiss/{rec_id}          → dismiss a recommendation
```

**UI principles:**
- Server-rendered HTML with minimal CSS (Pico CSS or classless CSS framework)
- `dir="auto"` on all text elements for BiDi
- Poster images from TMDB CDN: `https://image.tmdb.org/t/p/w200{poster_path}`
- Streaming provider icons from TMDB: `https://image.tmdb.org/t/p/original{logo_path}`
- TMDB attribution in footer

**Manual entry autocomplete:**
- JavaScript: `fetch('/search?q=' + input.value)` on keyup with 300ms debounce
- Backend: `tmdb_get(f"/search/multi?query={q}&language=he-IL")` → return top 5 as JSON
- Display: poster thumbnail + title + year + type badge

**Time estimate:** 4-6 hours.

---

### Step 6: Telegram Bot

**Goal:** Push notifications + disambiguation inline keyboards.

**File:** `bot/telegram_notifier.py`

**Implementation:** `python-telegram-bot` library in long-polling mode.

**Functions:**
```python
def send_new_season_alert(chat_id, series_title, season_number, provider_name=None):
    text = f"🍿 New Season!\n{series_title} Season {season_number} is now available"
    if provider_name:
        text += f" on {provider_name}"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Mark as watched", callback_data=f"watched_{title_id}"),
         InlineKeyboardButton("⏰ Remind later", callback_data=f"remind_{title_id}")]
    ])
    bot.send_message(chat_id, text, reply_markup=keyboard)

def send_disambiguation(chat_id, raw_title, candidates):
    text = f"❓ Which '{raw_title}' did you watch?"
    buttons = [[InlineKeyboardButton(
        f"{c.title} ({c.year}, {c.type})",
        callback_data=f"disambig_{title_id}_{c.tmdb_id}"
    )] for c in candidates[:3]]
    keyboard = InlineKeyboardMarkup(buttons)
    bot.send_message(chat_id, text, reply_markup=keyboard)
```

**Callback handler:** Process inline keyboard responses, update DB.

**Disambiguation timeout:** Cron checks for unresolved disambiguations > 48h → auto-pick highest TMDB popularity → log decision.

**Time estimate:** 2-3 hours.

---

### Step 7: Daily Cron + Onboarding Guide

**Goal:** Orchestration script + user guide.

**Files:**
- `cron/daily_check.py` — orchestrator
- `guides/netflix_export_guide.md` — screenshot-based, Hebrew + English

**Cron logic:**
```python
def daily_check():
    log("Starting daily check")

    # 1. Check new seasons
    alerts = check_new_seasons()
    for alert in alerts:
        send_new_season_alert(ADMIN_CHAT_ID, ...)

    # 2. Refresh streaming availability for all tracked titles
    titles = db.get_all_titles()
    for title in titles:
        update_availability(title.tmdb_id, title.tmdb_type)
        time.sleep(API_DELAY_SECONDS)

    # 3. Generate new recommendations (weekly, not daily)
    if datetime.now().weekday() == 0:  # Monday only
        for title in titles:
            generate_recommendations(title.id, title.tmdb_id, title.tmdb_type)
            time.sleep(API_DELAY_SECONDS)

    # 4. Timeout stale disambiguations
    resolve_stale_disambiguations()

    # 5. Error check
    if error_count >= 3:
        send_admin_alert(ADMIN_CHAT_ID, "TMDB API errors detected")

    log("Daily check complete")
```

**Crontab entry:**
```bash
0 6 * * * cd /path/to/popcorn && python cron/daily_check.py >> logs/cron.log 2>&1
```

**Onboarding guide structure:**
1. Open Netflix in browser → go to Account
2. Click Profile & Parental Controls → select YOUR profile
3. Click Viewing Activity
4. Scroll to bottom → click "Download All"
5. File saved as `NetflixViewingHistory.csv`
6. Go to Popcorn dashboard → click Upload → select the file
7. Wait for matching (progress bar shows status)
8. Review any flagged titles
9. Done!

Include screenshots. Provide guide in both Hebrew and English. This IS the onboarding — there's nothing else.

**Time estimate:** 2 hours.

---

## Total Estimated Build Time

| Step | Component | Hours |
|------|-----------|-------|
| 1 | DB + Config | 0.5 |
| 2 | CSV Parser | 1-2 |
| 3 | TMDB Matcher | 2-3 |
| 4 | Rec + Season + Availability | 3-4 |
| 5 | Dashboard | 4-6 |
| 6 | Telegram Bot | 2-3 |
| 7 | Cron + Guide | 2 |
| **Total** | | **15-20 hours** |

---

## File Plan (Create All At Once)

```
popcorn/
├── README.md
├── CHANGELOG.md
├── .env.example
├── requirements.txt
├── config.py
├── db/
│   └── schema.sql
├── ingestion/
│   ├── csv_parser.py
│   └── tmdb_matcher.py
├── engine/
│   ├── recommendations.py
│   ├── new_season_checker.py
│   └── availability.py
├── bot/
│   └── telegram_notifier.py
├── dashboard/
│   ├── app.py
│   ├── templates/
│   │   ├── base.html
│   │   ├── watch_next.html
│   │   ├── coming_soon.html
│   │   ├── library.html
│   │   └── review.html
│   └── static/
│       └── style.css
├── cron/
│   └── daily_check.py
├── guides/
│   ├── netflix_export_guide_en.md
│   └── netflix_export_guide_he.md
├── tests/
│   ├── test_csv_parser.py
│   ├── test_tmdb_matcher.py
│   └── test_recommendations.py
└── logs/
    └── .gitkeep
```

## requirements.txt

```
flask>=3.0
requests>=2.31
python-telegram-bot>=20.0
python-dateutil>=2.8
```

No other dependencies. SQLite is built into Python. No ORM. No Redis. No Docker.

---

## Definition of Done (v0.1)

- [ ] Upload Netflix CSV → titles appear in "My Library"
- [ ] "Watch Next" tab shows recommendations with posters
- [ ] "Coming Soon" tab shows series with new seasons
- [ ] Streaming provider icons visible on title cards
- [ ] Telegram bot sends new season notification
- [ ] Manual entry via autocomplete works
- [ ] Low-confidence matches surfaced for review
- [ ] Daily cron runs without errors for 3 consecutive days
- [ ] Non-technical user completes onboarding guide without help
- [ ] TMDB attribution visible in footer

---

*Build in order. Test each step. Don't jump ahead.*
