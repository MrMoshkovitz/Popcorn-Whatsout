# Popcorn — Claude Code Project Configuration

> Personal movie & TV tracker: Netflix CSV → TMDB matching → recommendations, new-season alerts, streaming availability. Dashboard + Telegram push. Single user. Zero effort after first upload.

## Philosophy: "Couch Potato Sovereignty"

The system serves the viewer's laziness with dignity. It suggests, never nags. It guesses smart, never forces precision. "Good enough" beats "perfectly accurate."

**Decision test:** "Would this feel like Popcorn, or like enterprise software?" If enterprise — cut it.

**Trade-off hierarchy** (when principles conflict):
1. Ships fast > Ships right
2. Good enough > Perfectly accurate
3. Simple UX > Powerful UX
4. One API source > Multiple sources
5. Manual fallback > Automated fallback
6. Daily updates > Real-time updates
7. SQLite > "Proper" database

---

## Hard Constraints

**YOU MUST follow these. No exceptions. No "just this once."**

1. **4 dependencies only:** `flask`, `requests`, `python-telegram-bot`, `python-dateutil` — nothing else in `requirements.txt`
2. **SQLite only, no ORM:** `import sqlite3`, parameterized queries with `?`, raw SQL. NEVER import sqlalchemy/peewee/alembic
3. **TMDB is sole data source:** all metadata, recommendations, streaming availability from TMDB API v3. No OMDB/Trakt/Watchmode fallbacks
4. **Single-user system:** no auth, no sessions, no multi-tenancy, no user registration
5. **Server-rendered only:** Flask + Jinja2 + Pico CSS. No React/Vue/npm/SPA/bundlers
6. **No infrastructure:** no Docker, no CI/CD, no Kubernetes, no Redis, no PostgreSQL. `python app.py` is the deployment
7. **TMDB rate limiting:** `time.sleep(0.2)` between EVERY TMDB API call — no exceptions
8. **BiDi:** `dir="auto"` on ALL text-displaying HTML elements
9. **TMDB attribution:** footer with logo + disclaimer on every dashboard page
10. **Secrets in `.env`:** API keys loaded via `config.py`, never hardcoded, `.env` in `.gitignore`

---

## NEVER Do These

- Add dependencies beyond requirements.txt
- Suggest ORM, Docker, microservices, Redis, PostgreSQL, message queues
- Add authentication, user management, sessions, OAuth
- Add dashboard filters, settings pages, "advanced mode", sort controls
- Add real-time polling, webhooks, "refresh now" buttons
- Build Telegram as an app (it's a push-only megaphone — no /commands, no browsing)
- Import from other streaming platforms (no scrapers, no browser extensions)
- Use f-strings, `.format()`, or string concatenation in SQL queries
- Skip the he-IL → en-US two-pass language search on TMDB calls
- Commit `.env` files or hardcode secrets
- Build v0.2 features in v0.1 (see Deferred Features below)

---

## Tech Stack

- **Python 3.11+**
- **Flask** — web framework, server-rendered Jinja2 templates
- **SQLite** — single `popcorn.db` file, `sqlite3` stdlib module
- **requests** — HTTP client for TMDB API
- **python-telegram-bot** — push notifications, inline keyboards, long-polling
- **python-dateutil** — date parsing with `dayfirst=True`
- **Pico CSS** — classless CSS framework (CDN link, no npm)
- **pytest** — test runner (dev dependency, NOT in requirements.txt)

---

## File Structure

```
popcorn/
├── config.py                          # .env loader, all constants
├── .env.example                       # Template for secrets
├── requirements.txt                   # 4 packages only
├── .gitignore
├── db/
│   └── schema.sql                     # 6 tables, indexes, CHECK constraints
├── ingestion/
│   ├── csv_parser.py                  # Netflix CSV → ParsedEntry dicts
│   └── tmdb_matcher.py                # ParsedEntry → MatchedTitle via TMDB
├── engine/
│   ├── recommendations.py             # Movie recs (top 5), TV recs (top 3), collections
│   ├── new_season_checker.py          # Detect new seasons for tracked series
│   └── availability.py                # Streaming providers for IL region
├── dashboard/
│   ├── app.py                         # Flask app, 10 routes
│   ├── templates/                     # base.html + 4 tab templates
│   └── static/style.css               # Minimal custom styles
├── bot/
│   └── telegram_notifier.py           # Push notifications + disambiguation
├── cron/
│   └── daily_check.py                 # Orchestrator: seasons → availability → recs → notify
├── guides/
│   ├── netflix_export_guide_en.md
│   └── netflix_export_guide_he.md
├── tests/
│   ├── test_csv_parser.py             # 6 test cases
│   ├── test_tmdb_matcher.py           # 8 test cases (mocked TMDB)
│   └── test_recommendations.py        # 6 test cases
└── logs/.gitkeep
```

---

## Database Schema

6 tables in `db/schema.sql`: `titles`, `watch_history`, `series_tracking`, `recommendations`, `streaming_availability`, `settings`

Key constraints:
- `titles`: UNIQUE(tmdb_id, tmdb_type)
- `watch_history`: UNIQUE(title_id, watch_date, season_number, episode_name)
- `series_tracking`: UNIQUE(title_id)
- `recommendations`: UNIQUE(source_title_id, recommended_tmdb_id)
- `streaming_availability`: UNIQUE(tmdb_id, tmdb_type, provider_name, monetization_type)

Full schema: `GroundProgressiveArchitecuture/Simplified-Architecture.md`

---

## Code Patterns

### TMDB API — ALL calls go through shared helper
```python
def tmdb_get(endpoint: str, params: dict = None) -> dict | None:
    time.sleep(API_DELAY_SECONDS)  # 0.2s — ALWAYS
    url = f"{TMDB_BASE_URL}{endpoint}"
    params = params or {}
    params["api_key"] = TMDB_API_KEY
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logging.error(f"TMDB API error: {endpoint} - {e}")
        return None
```

### Two-Pass Language Search
1. Always search `language=he-IL` first
2. If no results → fallback `language=en-US`
3. Watch providers: always `watch_region=IL`

### Confidence Scoring
```python
confidence = (SequenceMatcher(None, query.lower(), result_title.lower()).ratio() * 0.7) \
           + (min(popularity / 100, 1.0) * 0.3)
# >= 0.6 → match_status="auto"
# < 0.6  → match_status="review"
```

### SQLite Patterns
```python
# Connection
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# Queries — ALWAYS parameterized
cursor.execute("SELECT * FROM titles WHERE tmdb_id = ? AND tmdb_type = ?", (tmdb_id, tmdb_type))

# Upsert
cursor.execute("INSERT OR REPLACE INTO titles (...) VALUES (?, ?, ...)", (...))

# Batch — commit after batch, NEVER per row
for entry in entries:
    cursor.execute("INSERT INTO watch_history ...", (...))
conn.commit()
```

### Image URLs
- Posters: `https://image.tmdb.org/t/p/w200{poster_path}`
- Provider logos: `https://image.tmdb.org/t/p/original{logo_path}`

### Error Handling
- TMDB: try/except with logging, consecutive error counter, 3 errors → Telegram admin alert
- CSV parsing: skip malformed rows gracefully, log warnings
- DB: use context managers or explicit close

---

## Dashboard Routes (10 total)

```
GET  /                    → redirect to /watch-next
GET  /watch-next          → recommendations tab
GET  /coming-soon         → new seasons tab
GET  /library             → full watch history
GET  /review              → low-confidence matches needing review
POST /upload              → CSV upload + process (24h rate limit)
GET  /search?q=           → TMDB autocomplete JSON (300ms debounce, min 3 chars)
POST /add                 → manual title add from autocomplete
POST /resolve/{title_id}  → confirm/change TMDB match
POST /dismiss/{rec_id}    → dismiss a recommendation
```

---

## Build Order (7 Steps — Sequential, Don't Skip)

1. **DB + Config** → `db/schema.sql`, `config.py`, `.env.example`
2. **CSV Parser** → `ingestion/csv_parser.py` + tests
3. **TMDB Matcher** → `ingestion/tmdb_matcher.py` + tests
4. **Engines** → `engine/recommendations.py`, `new_season_checker.py`, `availability.py` + tests
5. **Dashboard** → `dashboard/app.py` + 5 templates + static/style.css
6. **Telegram Bot** → `bot/telegram_notifier.py`
7. **Cron + Docs** → `cron/daily_check.py` + `guides/`

**IMPORTANT:** Build in order. Test each step. Don't jump ahead.

---

## Testing

- **Runner:** `pytest tests/`
- **TMDB mocking:** `unittest.mock.patch` on `tmdb_get()` — NO real API calls in tests
- **DB testing:** in-memory SQLite (`sqlite3.connect(':memory:')`) with `schema.sql` applied
- **No `time.sleep` in tests** — mock it
- **pytest is a dev dependency** — not in requirements.txt

---

## Key Commands

```bash
# Run the dashboard
python dashboard/app.py

# Run tests
pytest tests/

# Run daily cron manually
python cron/daily_check.py

# Initialize database
sqlite3 popcorn.db < db/schema.sql

# Set up crontab
0 6 * * * cd /path/to/popcorn && python cron/daily_check.py >> logs/cron.log 2>&1
```

## Environment Variables (.env)

```
TMDB_API_KEY=your_tmdb_api_key
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_ADMIN_CHAT_ID=your_chat_id
```

Constants in `config.py`:
- `TMDB_BASE_URL = "https://api.themoviedb.org/3"`
- `TMDB_LANGUAGE_PRIMARY = "he-IL"`
- `TMDB_LANGUAGE_FALLBACK = "en-US"`
- `WATCH_REGION = "IL"`
- `MATCH_CONFIDENCE_THRESHOLD = 0.6`
- `API_DELAY_SECONDS = 0.2`
- `DISAMBIGUATION_TIMEOUT_HOURS = 48`

---

## The 7 Decision Principles (Quick Reference)

| # | Principle | One-Line Rule |
|---|-----------|---------------|
| 1 | Fuzzy Is Fine | 80% accurate now beats 99% never. Accept 1-in-10 errors. |
| 2 | One Screen, One Answer | No filters, no advanced mode. Three tabs, just scroll. |
| 3 | Stale Beats Silent | 24-32h data staleness is accepted. Label "Updated daily." |
| 4 | The CSV Is the Contract | Netflix CSV is the ONLY automated input. Everything else is manual. |
| 5 | Telegram Is the Megaphone | Push-only. No commands. No browsing. Not an app. |
| 6 | TMDB Is God (For Now) | Single source. No multi-sourcing. No fallback APIs. |
| 7 | Ship the Toy | Single user, single process, SQLite. `python app.py`. |

**Decision filter for "should we add X?":**
1. Does a non-technical viewer need this? NO → CUT
2. Can we ship without it and add later? YES → DEFER
3. Does it require a new API dependency? YES → CUT
4. Can I explain it in one sentence? NO → SIMPLIFY, YES → BUILD IT

Full principles + 36-problem decisions log: `GroundProgressiveArchitecuture/Philosophical-Grounding.md`

---

## Deferred Features (v0.2+ — BLOCK in v0.1)

- Multi-profile support
- Other streaming platform CSV imports
- Advanced recommendation algorithms (ML/NLP)
- Social features (sharing, friends, likes)
- Mobile app
- Dashboard filters, sort controls, settings page
- Telegram /commands or browsing
- Browser extensions
- PostgreSQL migration
- CI/CD pipeline

---

## Agent System

19 specialized agents in `.claude/agents/`. Full inventory, routing matrix, dependency graph: `.claude/agent-map.md`

### Authority Hierarchy
```
scope-guardian (supreme — can reject any change)
  ├── arch-validator (structural conformance)
  │     └── code-reviewer (implementation quality)
  └── dep-auditor (dependency conformance)
```
scope-guardian has **absolute veto**. If it rejects, nothing else matters.

### Key Agents
- **scope-guardian** — enforces philosophy, blocks over-engineering and scope creep
- **agent-router** — classifies tasks, routes to correct agent(s). Routes only, never decides.
- **Component agents** — db-config, csv-parser, tmdb-matcher, rec-engine, flask-dashboard, telegram-bot, daily-cron
- **Cross-cutting agents** — tmdb-api (API patterns), sqlite-ops (SQL patterns), bidi-handler (BiDi), test-runner (pytest)
- **Pipeline agents** — csv-import-pipeline, notification-pipeline
- **Quality agents** — arch-validator, code-reviewer, dep-auditor

### Agent Routing (Common Tasks)
| Task | Agent(s) |
|------|----------|
| New feature / add / implement | scope-guardian + arch-validator + code-reviewer + component agent |
| Bug fix / error | code-reviewer + component agent |
| Add package / dependency | dep-auditor + scope-guardian (likely rejection) |
| Database / schema | arch-validator + sqlite-ops + db-config |
| TMDB / API / matching | tmdb-api + code-reviewer + component agent |
| Dashboard / UI / template | flask-dashboard + bidi-handler |
| Tests / pytest | test-runner |
| Deploy / Docker / CI | scope-guardian (REJECTION) |

### Agent Teams (Experimental)

9 teams in `.claude/teams/`. Full mapping: `.claude/agent-teams-map.md`. Requires `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`.

- **Essential:** Engine Forge (Step 4), Dashboard Assembly (Step 5), CSV Import Pipeline (Steps 2+3), Quality Gate (all steps), Release Readiness (v0.1)
- **Recommended:** Integration Verification (after Steps 4+5+6)
- **Nice to have:** Notification Layer (Steps 6+7), Daily Refresh Pipeline, Test Suite

---

## Reference Documentation

All authoritative specs in `GroundProgressiveArchitecuture/`:

| Document | Contains |
|----------|----------|
| `Vision.md` | North star, data flow, success criteria |
| `Executive-Summary.md` | Scope summary, key decisions |
| `Simplified-Architecture.md` | Full DB schema, component specs, TMDB endpoints |
| `Implementation-Instructions.md` | 7-step build plan, test cases, file structure, DoD |
| `Philosophical-Grounding.md` | 7 Decision Principles, Decision Filter, 36-problem decisions log |
| `PRD.md` | Full product requirements (sections 1-25) |
