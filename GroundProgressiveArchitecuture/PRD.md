# 🍿 Popcorn — Product Requirements Document (PRD)

**Version:** v0.1
**Date:** March 2026
**Status:** Planning Complete — Ready for Implementation
**Methodology:** Grounded Progressive Architecture (GPA)

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Product Vision](#2-product-vision)
3. [Target User](#3-target-user)
4. [User Stories](#4-user-stories)
5. [Functional Requirements](#5-functional-requirements)
6. [Non-Functional Requirements](#6-non-functional-requirements)
7. [Data Model](#7-data-model)
8. [System Architecture](#8-system-architecture)
9. [API Dependencies](#9-api-dependencies)
10. [User Flows](#10-user-flows)
11. [Dashboard Specification](#11-dashboard-specification)
12. [Telegram Bot Specification](#12-telegram-bot-specification)
13. [Matching Engine Specification](#13-matching-engine-specification)
14. [Recommendation Engine Specification](#14-recommendation-engine-specification)
15. [Streaming Availability Specification](#15-streaming-availability-specification)
16. [Cron & Background Jobs](#16-cron--background-jobs)
17. [Onboarding Guide Requirements](#17-onboarding-guide-requirements)
18. [Scope Boundaries](#18-scope-boundaries)
19. [Known Limitations & Accepted Risks](#19-known-limitations--accepted-risks)
20. [Decision Principles](#20-decision-principles)
21. [Success Criteria](#21-success-criteria)
22. [Implementation Plan](#22-implementation-plan)
23. [File Structure](#23-file-structure)
24. [Dependencies](#24-dependencies)
25. [Future Considerations (v0.2+)](#25-future-considerations-v02)

---

## 1. Problem Statement

A person finishes binge-watching a great series. Six months later, a new season drops — they miss it entirely. A sequel to a movie they loved comes out — they find out a year late. They want something similar to watch tonight — but scrolling Netflix for 20 minutes yields nothing.

Their Netflix viewing history holds years of taste data. It does nothing for them.

**Core pain points:**
- No awareness when new seasons of watched series are released
- No awareness of sequels/prequels to movies they enjoyed
- No personalized "watch next" recommendations based on actual history
- No single place to see where content is available to stream
- Content spread across platforms with no unified view

---

## 2. Product Vision

### Name: Popcorn

Casual. Fun. Zero pretension. Anchors every decision to the couch experience.

### One-Line Vision

A personal movie & TV tracking system that turns your Netflix history into smart recommendations, new-season alerts, and "where to watch" answers — with zero ongoing effort.

### Core User Promise

**"Never miss a sequel, new season, or great recommendation — without lifting a finger after the first upload."**

### Philosophy: "Couch Potato Sovereignty"

The system serves the viewer's laziness with dignity. It suggests, never nags. It guesses smart, never forces precision. It embraces "good enough" over "perfectly accurate."

### Minimal Viable Interaction Loop

```
1. User exports Netflix CSV (guided by screenshot-based onboarding)
2. User uploads CSV to Popcorn dashboard
3. System fuzzy-matches titles to TMDB
4. Dashboard populates: "Watch Next" / "Coming Soon" / "My Library"
5. Daily cron checks for new seasons + streaming availability changes
6. Telegram bot pushes notifications for actionable changes
7. User can manually add non-Netflix content via autocomplete search
```

---

## 3. Target User

### Primary Persona

**Name:** Non-technical Netflix viewer in Israel
**Behavior:** Watches 5-15 hours/week across Netflix and 1-2 other platforms. Does not use Letterboxd, Trakt, or any tracking tool. Discovers content through word of mouth and platform algorithms.
**Pain:** Regularly misses new seasons, sequels, and content they'd enjoy. Forgets what they've watched.
**Tech comfort:** Can follow a screenshot-based guide. Uses Telegram daily. Comfortable with basic web apps.

### Secondary Persona

**Name:** Small friend group (3-5 people) sharing recommendations informally.
**Note:** v0.1 is single-user. Friend-group features are out of scope.

### Explicitly NOT For

- Power users wanting Letterboxd/Trakt-level customization
- Users expecting real-time notifications (daily cadence accepted)
- Users across 5+ streaming platforms wanting unified management
- Users wanting social features (ratings, reviews, shared lists)

---

## 4. User Stories

### Onboarding (One-Time)

| ID | Story | Priority |
|----|-------|----------|
| US-01 | As a user, I want a step-by-step guide with screenshots to export my Netflix viewing history CSV so I can set up Popcorn without technical knowledge. | **P0** |
| US-02 | As a user, I want to upload my Netflix CSV and see my viewing history populated automatically so I don't have to enter titles manually. | **P0** |
| US-03 | As a user, I want to review titles the system isn't confident about so I can correct wrong matches. | **P0** |

### Daily Use

| ID | Story | Priority |
|----|-------|----------|
| US-04 | As a user, I want to see a "Watch Next" list of recommendations based on what I've watched so I can find new content easily. | **P0** |
| US-05 | As a user, I want to see which streaming platform each title is available on in Israel so I know where to watch it. | **P0** |
| US-06 | As a user, I want to be notified via Telegram when a series I watched gets a new season so I don't miss it. | **P0** |
| US-07 | As a user, I want to see a "Coming Soon" section for unreleased seasons of shows I'm tracking so I can look forward to them. | **P1** |
| US-08 | As a user, I want to manually add titles I watched on other platforms so my recommendations include all my viewing. | **P1** |
| US-09 | As a user, I want the manual entry to have autocomplete from TMDB so I don't misspell titles. | **P1** |
| US-10 | As a user, I want to dismiss recommendations I'm not interested in so the list stays relevant. | **P2** |
| US-11 | As a user, I want to re-upload a newer Netflix CSV and have it merge with my existing data so I stay up to date. | **P2** |

### Notifications

| ID | Story | Priority |
|----|-------|----------|
| US-12 | As a user, I want Telegram notifications for new season releases so I hear about them within 48 hours. | **P0** |
| US-13 | As a user, I want Telegram to ask me which title I meant when the system isn't sure, with button choices, so I can resolve ambiguity quickly. | **P1** |
| US-14 | As a user, I want Telegram to notify me of new movie recommendations weekly so I get fresh ideas without spam. | **P2** |

---

## 5. Functional Requirements

### FR-01: Netflix CSV Import

| Req | Description |
|-----|-------------|
| FR-01.1 | Accept CSV files from Netflix Viewing Activity page (`/viewingactivity` → Download All). |
| FR-01.2 | Parse CSV with 2 columns: `Title` (string) and `Date` (date). |
| FR-01.3 | Handle date formats with `dayfirst=True` for Israeli locale compatibility. |
| FR-01.4 | Split `Title` on `:` delimiter to extract show name, season number, and episode name. |
| FR-01.5 | Detect series entries by presence of season pattern (`Season X`, `Part X`, `עונה X`, `Staffel X`). |
| FR-01.6 | Entries without season patterns are treated as movies. |
| FR-01.7 | Deduplicate by `parsed_name` before TMDB matching to minimize API calls. |
| FR-01.8 | Show progress bar during import processing. |
| FR-01.9 | Delete uploaded CSV file from server after processing completes. |
| FR-01.10 | Limit to one CSV upload per 24-hour period. |
| FR-01.11 | Re-upload merges via upsert on `(title + date)` composite. Manual entries are never overwritten. |

### FR-02: TMDB Title Matching

| Req | Description |
|-----|-------------|
| FR-02.1 | For each unique parsed title, query TMDB Search API. |
| FR-02.2 | Series entries search `/search/tv` first; movies search `/search/movie` first. |
| FR-02.3 | Primary search uses `language=he-IL`. Fallback search uses `language=en-US`. |
| FR-02.4 | If primary type yields no results, search the opposite type as fallback. |
| FR-02.5 | Select result #1 by TMDB popularity score. |
| FR-02.6 | Calculate confidence score: `(string_similarity × 0.7) + (normalized_popularity × 0.3)`. |
| FR-02.7 | Confidence ≥ 0.6 → `match_status = "auto"` (accepted). |
| FR-02.8 | Confidence < 0.6 → `match_status = "review"` (flagged for user). |
| FR-02.9 | No match found → `match_status = "review"` with empty TMDB data. |
| FR-02.10 | Rate limit: 200ms delay between TMDB API calls. |
| FR-02.11 | Store TMDB ID, type, title (en + he), poster path, confidence, and match status. |

### FR-03: Dashboard

| Req | Description |
|-----|-------------|
| FR-03.1 | Three tabs: "Watch Next", "Coming Soon", "My Library". |
| FR-03.2 | **Watch Next:** Display recommendations + unwatched sequels, ordered by TMDB score. |
| FR-03.3 | **Coming Soon:** Display series with announced but not-yet-aired seasons. |
| FR-03.4 | **My Library:** Display all watched content with poster, title, and watch date. |
| FR-03.5 | Each title card shows: poster thumbnail, title (he/en), streaming provider icons. |
| FR-03.6 | Low-confidence review banner: "X titles need your review" at top of page when `match_status = 'review'` entries exist. |
| FR-03.7 | Review flow: show title with "Correct" button or "Search Again" option. |
| FR-03.8 | CSV upload via file picker with drag-and-drop support. |
| FR-03.9 | Manual entry: search bar with TMDB autocomplete (debounce 300ms, min 3 chars, top 5 results). |
| FR-03.10 | Autocomplete results show poster thumbnail + title + year + type badge. |
| FR-03.11 | Dismiss button on recommendation cards. |
| FR-03.12 | All text elements use `dir="auto"` for Hebrew/English BiDi support. |
| FR-03.13 | TMDB attribution in footer: logo + required disclaimer text. |
| FR-03.14 | "Updated daily" label on streaming availability data. |
| FR-03.15 | No filters, no sort options, no search within tabs. Scroll only. |

### FR-04: Recommendation Engine

| Req | Description |
|-----|-------------|
| FR-04.1 | For each watched movie: fetch `/movie/{id}/recommendations` → store top 5. |
| FR-04.2 | For each watched movie with a collection: fetch `/collection/{id}` → flag unwatched entries as sequel/prequel. |
| FR-04.3 | For each watched TV series: fetch `/tv/{id}/recommendations` → store top 3. |
| FR-04.4 | Exclude titles already in user's library from recommendations. |
| FR-04.5 | Recommendations refresh weekly (Monday cron). |
| FR-04.6 | Dismissed recommendations are not re-generated. |

### FR-05: New Season Detection

| Req | Description |
|-----|-------------|
| FR-05.1 | Track all series where user has watched at least one episode. |
| FR-05.2 | Series with `max_watched_season < total_seasons_tmdb` → "new season available". |
| FR-05.3 | Daily check: query `/tv/{id}` for all series with `status = 'watching'`. |
| FR-05.4 | When new season detected → create Telegram notification. |
| FR-05.5 | Season "watched" threshold: user watched ≥80% of episodes in a season. |

### FR-06: Streaming Availability

| Req | Description |
|-----|-------------|
| FR-06.1 | For each title in library: query TMDB watch providers with `watch_region=IL`. |
| FR-06.2 | Store provider name, logo path, and monetization type (flatrate/rent/buy). |
| FR-06.3 | Display provider icons on title cards in dashboard. |
| FR-06.4 | Refresh daily via cron. |
| FR-06.5 | Clear stale availability data on each refresh (full replace per title). |

### FR-07: Telegram Bot

| Req | Description |
|-----|-------------|
| FR-07.1 | Push-only operation. No user-initiated commands in v0.1. |
| FR-07.2 | New season alert: title, season number, streaming provider (if available), inline buttons [Mark as watched] [Remind later]. |
| FR-07.3 | Disambiguation prompt: raw title, up to 3 candidate matches with title/year/type, inline keyboard selection. |
| FR-07.4 | Disambiguation timeout: 48 hours → auto-pick highest TMDB popularity, log the auto-decision. |
| FR-07.5 | Weekly recommendation digest: up to 5 new recommendations with poster + title. |
| FR-07.6 | Admin error alert: if daily cron encounters 3+ consecutive TMDB API errors. |
| FR-07.7 | Long-polling mode (not webhook). |

---

## 6. Non-Functional Requirements

| Category | Requirement |
|----------|-------------|
| **Performance** | CSV import of 2000 entries completes within 10 minutes (including TMDB matching). |
| **Performance** | Dashboard pages load within 2 seconds on broadband connection. |
| **Performance** | Daily cron completes within 30 minutes for a library of 500 titles. |
| **Availability** | Personal tool — no SLA. Acceptable downtime: hours/days for maintenance. |
| **Scalability** | Single-user, single-instance. No scaling architecture required. |
| **Security** | Uploaded CSV deleted after processing. Only TMDB IDs stored, not raw titles. |
| **Security** | Telegram bot token and TMDB API key stored in `.env`, never committed to git. |
| **Security** | One CSV upload per 24h to prevent API abuse. |
| **Localization** | Dashboard supports Hebrew (RTL) and English (LTR) mixed content via `dir="auto"`. |
| **Localization** | TMDB queries use `he-IL` as primary language, `en-US` as fallback. |
| **Localization** | Streaming availability filtered to Israel (`watch_region=IL`). |
| **Localization** | Onboarding guide provided in both Hebrew and English. |
| **Compliance** | TMDB attribution logo + disclaimer in dashboard footer (required by TMDB ToS). |
| **Compliance** | TMDB API used under non-commercial free tier terms. |
| **Data freshness** | Streaming availability: updated daily (24-32h staleness accepted and labeled). |
| **Data freshness** | New season detection: checked daily at 06:00. |
| **Data freshness** | Recommendations: refreshed weekly (Mondays). |

---

## 7. Data Model

### Entity Relationship

```
titles (1) ──── (N) watch_history
titles (1) ──── (1) series_tracking       [only for tmdb_type='tv']
titles (1) ──── (N) recommendations       [as source]
titles (1) ──── (N) streaming_availability [via tmdb_id]
```

### Table: `titles`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PK, AUTO | Internal ID |
| tmdb_id | INTEGER | NOT NULL | TMDB identifier |
| tmdb_type | TEXT | CHECK('movie','tv') | Content type |
| title_en | TEXT | | English title |
| title_he | TEXT | NULLABLE | Hebrew title |
| poster_path | TEXT | NULLABLE | TMDB poster path |
| confidence | REAL | DEFAULT 1.0 | Match confidence score (0.0-1.0) |
| match_status | TEXT | CHECK('auto','review','manual') | How the match was made |
| source | TEXT | CHECK('csv','manual') | How the title entered the system |
| created_at | TIMESTAMP | DEFAULT NOW | When added |

**Unique constraint:** `(tmdb_id, tmdb_type)`

### Table: `watch_history`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PK, AUTO | Internal ID |
| title_id | INTEGER | FK → titles.id | Parent title |
| raw_csv_title | TEXT | | Original CSV string (for debugging) |
| watch_date | DATE | NOT NULL | When watched |
| season_number | INTEGER | NULLABLE | Season if applicable |
| episode_name | TEXT | NULLABLE | Episode name if applicable |

**Unique constraint:** `(title_id, watch_date, season_number, episode_name)`

### Table: `series_tracking`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PK, AUTO | Internal ID |
| title_id | INTEGER | FK → titles.id, UNIQUE | Parent title |
| tmdb_id | INTEGER | NOT NULL | TMDB series ID |
| total_seasons_tmdb | INTEGER | | Latest season count from TMDB |
| max_watched_season | INTEGER | | Highest season user has watched |
| last_checked | TIMESTAMP | | Last TMDB check time |
| status | TEXT | CHECK('watching','completed','dropped') | Tracking status |

### Table: `recommendations`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PK, AUTO | Internal ID |
| source_title_id | INTEGER | FK → titles.id | Title that generated this rec |
| recommended_tmdb_id | INTEGER | NOT NULL | TMDB ID of recommended content |
| recommended_type | TEXT | NOT NULL | 'movie' or 'tv' |
| recommended_title | TEXT | | Display title |
| poster_path | TEXT | NULLABLE | TMDB poster path |
| tmdb_recommendation_score | REAL | | TMDB's own ranking score |
| status | TEXT | CHECK('unseen','dismissed','watched') | User action |
| created_at | TIMESTAMP | DEFAULT NOW | When generated |

**Unique constraint:** `(source_title_id, recommended_tmdb_id)`

### Table: `streaming_availability`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PK, AUTO | Internal ID |
| tmdb_id | INTEGER | NOT NULL | TMDB ID |
| tmdb_type | TEXT | NOT NULL | 'movie' or 'tv' |
| provider_name | TEXT | NOT NULL | e.g., "Netflix", "Apple TV+" |
| provider_logo_path | TEXT | NULLABLE | TMDB logo path |
| monetization_type | TEXT | | 'flatrate', 'rent', 'buy' |
| last_updated | TIMESTAMP | DEFAULT NOW | When last refreshed |

**Unique constraint:** `(tmdb_id, tmdb_type, provider_name, monetization_type)`

### Table: `settings`

| Column | Type | Description |
|--------|------|-------------|
| key | TEXT (PK) | Setting name |
| value | TEXT | Setting value (JSON-encoded if complex) |

**Initial settings:**
- `last_csv_upload` → timestamp (rate limiting)
- `telegram_chat_id` → user's chat ID
- `onboarding_complete` → boolean

### Indexes

```sql
CREATE INDEX idx_watch_history_title ON watch_history(title_id);
CREATE INDEX idx_series_tracking_status ON series_tracking(status);
CREATE INDEX idx_recommendations_status ON recommendations(status);
CREATE INDEX idx_streaming_tmdb ON streaming_availability(tmdb_id, tmdb_type);
```

---

## 8. System Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         POPCORN v0.1                            │
│                                                                 │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────────┐  │
│  │ CSV Parser   │───▶│ TMDB Matcher │───▶│ SQLite Database   │  │
│  │ (one-time)   │    │ (fuzzy)      │    │ (popcorn.db)      │  │
│  └─────────────┘    └──────────────┘    └─────────┬─────────┘  │
│                                               │   │   │        │
│                           ┌───────────────────┘   │   └─────┐  │
│                           ▼                       ▼         ▼  │
│                     ┌──────────┐         ┌──────────┐ ┌──────┐ │
│                     │Dashboard │         │Daily Cron│ │TG Bot│ │
│                     │ (Flask)  │         │          │ │(push)│ │
│                     └────┬─────┘         └────┬─────┘ └──┬───┘ │
│                          │                    │          │      │
└──────────────────────────┼────────────────────┼──────────┼──────┘
                           │                    │          │
                      Browser              TMDB API   Telegram API
```

### Data Flow

```
INGESTION FLOW (one-time + re-upload):
  Netflix CSV → csv_parser → [ParsedEntry] → tmdb_matcher → [MatchedTitle] → SQLite

DAILY CRON FLOW:
  series_tracking (watching) → TMDB /tv/{id} → compare seasons → alert if new
  all titles → TMDB /watch/providers → update streaming_availability
  (weekly) all titles → TMDB /recommendations → update recommendations

DASHBOARD FLOW:
  Browser → Flask routes → SQLite queries → Jinja2 templates → HTML response
  Manual entry → TMDB /search/multi → autocomplete JSON → user selects → SQLite

TELEGRAM FLOW:
  Cron detects change → telegram_notifier → Telegram Bot API → user device
  User taps inline button → callback handler → update SQLite
```

### Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Language | Python 3.11+ | Primary language, fast prototyping |
| Database | SQLite | Zero ops, single-user, file-based backup |
| Web framework | Flask | Server-rendered HTML, simple routing, Jinja2 |
| HTTP client | requests | TMDB API calls |
| Telegram | python-telegram-bot v20+ | Async, inline keyboards, long-polling |
| Date parsing | python-dateutil | Locale-aware date parsing |
| CSS | Pico CSS or classless framework | Minimal, responsive, no build step |
| Deployment | Single VPS, `python app.py` | No Docker, no reverse proxy |
| Scheduling | System crontab | `0 6 * * *` for daily checks |

---

## 9. API Dependencies

### TMDB (The Movie Database)

| Endpoint | Purpose | Frequency |
|----------|---------|-----------|
| `GET /search/movie` | Match movie titles from CSV | On import |
| `GET /search/tv` | Match series titles from CSV | On import |
| `GET /search/multi` | Dashboard autocomplete | On manual entry |
| `GET /movie/{id}` | Movie details + collection info | On import + weekly |
| `GET /movie/{id}/recommendations` | Movie recommendations | Weekly |
| `GET /collection/{id}` | Sequel/prequel detection | Weekly |
| `GET /tv/{id}` | Series details + season count | Daily |
| `GET /tv/{id}/recommendations` | Series recommendations | Weekly |
| `GET /movie/{id}/watch/providers` | Streaming availability (IL) | Daily |
| `GET /tv/{id}/watch/providers` | Streaming availability (IL) | Daily |

**Rate limits:** ~50 req/sec (CDN-enforced), ~40 req/10sec (legacy, currently disabled). Our 200ms delay = ~5 req/sec — well within limits.

**Cost:** Free for non-commercial use with TMDB attribution.

**Attribution required:**
```
"This product uses the TMDB API but is not endorsed or certified by TMDB."
+ TMDB logo in dashboard footer
```

**Key parameters:**
- `language=he-IL` (primary) / `language=en-US` (fallback)
- `watch_region=IL` (streaming availability)

**Streaming data source:** TMDB's watch providers endpoint wraps JustWatch data. JustWatch sends TMDB a daily export. After TMDB processing + API cache, data is ~24-32 hours behind reality. This is accepted and labeled.

### Telegram Bot API

| Method | Purpose | Frequency |
|--------|---------|-----------|
| `sendMessage` | Push notifications with inline keyboards | On cron events |
| `answerCallbackQuery` | Respond to inline button presses | On user interaction |
| `getUpdates` | Long-polling for user responses | Continuous |

**Cost:** Free.
**Rate limit:** 30 messages/second (irrelevant for single-user).
**Mode:** Long-polling (not webhook) — simpler setup, no SSL required.

### Netflix CSV (Not an API)

**Source:** `https://www.netflix.com/viewingactivity` → "Download All" button.
**Format:** CSV with 2 columns: `Title` (string), `Date` (date string).
**Title format examples:**
```
"Breaking Bad: Season 1: Pilot"           → Series with season + episode
"Inception"                                → Movie (no colon)
"Mission: Impossible - Fallout"            → Movie with colon in name
"הכלה מאיסטנבול: עונה 1: פרק 3"           → Hebrew series
"Black Mirror: Bandersnatch"               → Special (no season number)
```
**Date format:** Varies by user locale. US = `MM/DD/YY`, EU/IL = `DD/MM/YY`.
**Limitations:** No genre, no TMDB ID, no runtime, no watch percentage, no content type. Per-profile only.
**Risk:** Netflix can change or remove this export at any time.

---

## 10. User Flows

### Flow 1: First-Time Setup (Onboarding)

```
User reads onboarding guide (screenshot-based, HE + EN)
    │
    ▼
User exports CSV from Netflix Viewing Activity page
    │
    ▼
User opens Popcorn dashboard (http://localhost:8080)
    │
    ▼
User uploads CSV via file picker / drag-and-drop
    │
    ▼
System parses CSV → deduplicates → matches titles against TMDB
    │                                (progress bar shown)
    ▼
System populates: titles, watch_history, series_tracking
    │
    ▼
IF low-confidence matches exist:
    Banner: "X titles need your review"
    User reviews each: [Correct] or [Search Again → pick from results]
    │
    ▼
Dashboard populated → "Watch Next" tab shows first recommendations
    │
    ▼
User sends /start to Telegram bot → system stores chat_id
    │
    ▼
Onboarding complete. Daily cron handles everything from here.
```

### Flow 2: Daily Automated Check

```
06:00 — Cron triggers daily_check.py
    │
    ├──▶ For each series (status='watching'):
    │       Query TMDB /tv/{id}
    │       IF new season detected:
    │           Update series_tracking
    │           Send Telegram new season alert
    │
    ├──▶ For each title:
    │       Query TMDB watch providers (watch_region=IL)
    │       Replace streaming_availability records
    │
    ├──▶ IF Monday:
    │       For each title:
    │           Query TMDB /recommendations
    │           Upsert new recommendations
    │           Send weekly Telegram digest
    │
    ├──▶ Resolve stale disambiguations (>48h):
    │       Auto-pick highest TMDB popularity
    │       Log auto-decision
    │
    └──▶ IF 3+ consecutive TMDB errors:
            Send admin Telegram alert
```

### Flow 3: Manual Title Entry

```
User clicks search bar in dashboard
    │
    ▼
User types ≥3 characters
    │
    ▼
Debounce 300ms → GET /search?q={query}
    │
    ▼
Backend queries TMDB /search/multi?query={q}&language=he-IL
    │
    ▼
Return top 5 results as JSON: poster + title + year + type
    │
    ▼
User clicks desired result
    │
    ▼
POST /add → insert into titles (source='manual') + watch_history
    │
    ▼
Title appears in "My Library" tab immediately
```

### Flow 4: Telegram Disambiguation

```
Cron finds low-confidence match during import
    │
    ▼
Bot sends: "Which 'Crash' did you watch on 12/03/2024?"
    [Crash (2004 Movie)] [Crash (2008 TV Series)] [Neither]
    │
    ├──▶ User taps a button within 48h:
    │       Update titles record with selected TMDB ID
    │       Set match_status = 'manual'
    │
    └──▶ No response after 48h:
            Auto-pick highest TMDB popularity
            Set match_status = 'auto'
            Log: "Auto-resolved: {raw_title} → {picked_title}"
```

---

## 11. Dashboard Specification

### Layout

```
┌─────────────────────────────────────────────────┐
│  🍿 Popcorn         [Upload CSV] [+ Add Title]  │
├─────────────────────────────────────────────────┤
│  ⚠️ 3 titles need your review → [Review Now]    │  ← Banner (conditional)
├──────────┬──────────────┬───────────────────────┤
│Watch Next│  Coming Soon │      My Library        │  ← Tabs
├──────────┴──────────────┴───────────────────────┤
│                                                  │
│  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐        │
│  │Poster│  │Poster│  │Poster│  │Poster│        │
│  │      │  │      │  │      │  │      │        │
│  │Title │  │Title │  │Title │  │Title │        │
│  │🎬 NF │  │🎬 AT │  │🎬 NF │  │🎬 DP │        │  ← Provider icons
│  │[Dismiss]│       │         │        │        │
│  └──────┘  └──────┘  └──────┘  └──────┘        │
│                                                  │
│  ... (scroll for more)                           │
│                                                  │
├─────────────────────────────────────────────────┤
│  Powered by TMDB | This product uses the TMDB   │
│  API but is not endorsed or certified by TMDB.   │
│  Updated daily.                                  │
└─────────────────────────────────────────────────┘
```

### Routes

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Redirect to `/watch-next` |
| GET | `/watch-next` | Recommendations tab |
| GET | `/coming-soon` | New/upcoming seasons tab |
| GET | `/library` | Full watch history |
| GET | `/review` | Low-confidence match review |
| POST | `/upload` | CSV upload + processing |
| GET | `/search?q={query}` | TMDB autocomplete (returns JSON) |
| POST | `/add` | Manual title add from autocomplete |
| POST | `/resolve/{title_id}` | Confirm or change TMDB match |
| POST | `/dismiss/{rec_id}` | Dismiss a recommendation |

### Title Card Components

Each card displays:
- **Poster:** `https://image.tmdb.org/t/p/w200{poster_path}` (fallback: placeholder)
- **Title:** Hebrew if available, English otherwise. `dir="auto"` for BiDi.
- **Year:** Release year from TMDB.
- **Type badge:** 🎬 Movie or 📺 TV Series.
- **Provider icons:** Small logos from TMDB CDN. Flatrate providers only (no rent/buy in v0.1 cards).
- **Action button:** Context-dependent (Dismiss for recs, Mark Watched for coming soon).

### Technology

- Flask + Jinja2 (server-rendered)
- Pico CSS (or equivalent classless framework — zero JavaScript build step)
- Vanilla JS only for: autocomplete debounce, file upload progress
- No React, no Vue, no build tools
- Mobile-responsive via CSS framework defaults

---

## 12. Telegram Bot Specification

### Message Templates

**New Season Alert:**
```
🍿 New Season Alert!

Breaking Bad — Season 6 is now available!
📺 Available on: Netflix

[✅ Mark as watched]  [⏰ Remind later]
```

**Disambiguation Prompt:**
```
❓ Help me match this title

Your Netflix history includes: "Crash"
Which one did you watch on 12/03/2024?

[1. Crash (2004 Movie) ⭐ 7.3]
[2. Crash (2008 TV Series) ⭐ 6.1]
[3. Neither — skip this one]
```

**Weekly Recommendation Digest:**
```
🎬 Weekly Picks for You

Based on what you've been watching:

1. Interstellar (2014) — Available on Netflix
2. The Prestige (2006) — Available on Apple TV+
3. Arrival (2016) — Rent on Google Play

Enjoy your weekend! 🍿
```

**Admin Error Alert:**
```
⚠️ Popcorn Admin Alert

Daily cron encountered 3+ consecutive TMDB API errors.
Last error: {error_message}
Time: {timestamp}

Check logs at: logs/cron.log
```

### Inline Keyboard Callbacks

| Callback Data Pattern | Action |
|----------------------|--------|
| `watched_{title_id}` | Update series_tracking.max_watched_season |
| `remind_{title_id}` | No action — will re-notify next day |
| `disambig_{title_id}_{tmdb_id}` | Update title's tmdb_id + set match_status='manual' |
| `skip_{title_id}` | Set match_status='review' (stays unresolved) |
| `dismiss_{rec_id}` | Set recommendation status='dismissed' |

### Bot Behavior Rules

- No `/commands` supported. Bot is push-only.
- If user sends any text message → reply: "🍿 I only send notifications! Visit your dashboard for full control: {dashboard_url}"
- Long-polling mode. Single-threaded.
- Graceful handling of Telegram API downtime (log + retry on next cron).

---

## 13. Matching Engine Specification

### Algorithm

```
INPUT: ParsedEntry { parsed_name, is_likely_series }

STEP 1: Determine search order
  IF is_likely_series → [tv, tv_en, movie, movie_en]
  ELSE               → [movie, movie_en, tv, tv_en]

STEP 2: Sequential search with early exit
  FOR EACH (type, language) in search_order:
    results = TMDB_SEARCH(type, parsed_name, language)
    IF results is not empty → BREAK

STEP 3: Select best result
  candidate = results[0]  (highest TMDB popularity)

STEP 4: Calculate confidence
  string_sim = SequenceMatcher(parsed_name.lower(), candidate.title.lower()).ratio()
  pop_factor = min(candidate.popularity / 100, 1.0)
  confidence = (string_sim × 0.7) + (pop_factor × 0.3)

STEP 5: Classify
  IF confidence >= 0.6 → match_status = "auto"
  IF confidence <  0.6 → match_status = "review"
  IF no results at all → match_status = "review", tmdb_id = NULL

OUTPUT: MatchedTitle { tmdb_id, tmdb_type, confidence, match_status }
```

### Search Order Matrix

| Parsed As | Search 1 | Search 2 | Search 3 | Search 4 |
|-----------|----------|----------|----------|----------|
| Series | /search/tv (he-IL) | /search/tv (en-US) | /search/movie (he-IL) | /search/movie (en-US) |
| Movie | /search/movie (he-IL) | /search/movie (en-US) | /search/tv (he-IL) | /search/tv (en-US) |

### Expected Accuracy

- **Auto-matched correctly:** ~80% of titles
- **Auto-matched incorrectly:** ~5-10% (user can correct in review)
- **Flagged for review:** ~10-15%
- **No match found:** ~1-3% (very obscure or removed content)

These numbers are estimates. Actual accuracy depends on the user's library composition (Hollywood content matches better than Israeli niche content).

---

## 14. Recommendation Engine Specification

### Sources

| Source | Endpoint | Max Results Stored | Refresh |
|--------|----------|--------------------|---------|
| Movie recommendations | `/movie/{id}/recommendations` | 5 per source | Weekly |
| Movie collection (sequels) | `/collection/{id}` | All unwatched | Weekly |
| TV recommendations | `/tv/{id}/recommendations` | 3 per source | Weekly |

### Deduplication Rules

- A recommended title already in the user's library → skip
- A recommended title already in the recommendations table (any source) → keep existing, don't duplicate
- A dismissed recommendation → never re-insert

### Ordering in Dashboard

Recommendations displayed by `tmdb_recommendation_score` descending. No custom scoring algorithm. TMDB's ranking is the ranking.

### Collection Handling

TMDB organizes movie franchises into "collections" (e.g., "The Dark Knight Collection"):
1. When processing a movie, check if `details.belongs_to_collection` exists
2. If yes, fetch the collection
3. Any movie in the collection NOT in the user's library → insert as recommendation with label context (sequel/prequel)

TV franchises (spin-offs like Better Call Saul → Breaking Bad) are NOT handled. TMDB has no reliable franchise graph for TV. Deferred.

---

## 15. Streaming Availability Specification

### Data Source

TMDB watch providers endpoint, which wraps JustWatch data:
- `GET /movie/{id}/watch/providers` → filter `results.IL`
- `GET /tv/{id}/watch/providers` → filter `results.IL`

### Data Structure from TMDB

```json
{
  "results": {
    "IL": {
      "link": "https://www.themoviedb.org/movie/xxx/watch?locale=IL",
      "flatrate": [
        { "provider_name": "Netflix", "logo_path": "/xxx.jpg", "provider_id": 8 }
      ],
      "rent": [...],
      "buy": [...]
    }
  }
}
```

### Storage Strategy

Full replace per title on each daily refresh:
1. DELETE all `streaming_availability` records WHERE `tmdb_id = X AND tmdb_type = Y`
2. INSERT new records from TMDB response
3. Update `last_updated` timestamp

### Display Priority

Dashboard cards show `flatrate` providers only (subscription streaming). Rent and buy options stored but not displayed on cards in v0.1 — could be shown on a detail view later.

### Known Limitations

- Data is 24-32h behind JustWatch
- Israeli streaming market coverage may be spotty for local services (HOT, YES, Partner TV)
- Some titles may show no providers if not available for streaming in IL
- Pre-launch validation required: test 20 popular titles, expect ≥50% coverage

---

## 16. Cron & Background Jobs

### Daily Job: `daily_check.py`

**Schedule:** `0 6 * * *` (6:00 AM daily, system crontab)

**Execution order:**
```
1. NEW SEASON CHECK
   - Query: series_tracking WHERE status = 'watching'
   - For each: GET /tv/{tmdb_id}
   - If total_seasons increased: update DB + send Telegram alert
   - Rate: 200ms delay between calls

2. STREAMING AVAILABILITY REFRESH
   - Query: all titles
   - For each: GET /{type}/{tmdb_id}/watch/providers
   - Full replace in streaming_availability table
   - Rate: 200ms delay between calls

3. RECOMMENDATIONS REFRESH (Mondays only)
   - Query: all titles
   - For each movie: GET /movie/{id}/recommendations + /collection/{id}
   - For each series: GET /tv/{id}/recommendations
   - Upsert into recommendations table
   - Send weekly Telegram digest
   - Rate: 200ms delay between calls

4. DISAMBIGUATION CLEANUP
   - Query: unresolved disambiguations older than 48h
   - Auto-pick highest TMDB popularity
   - Log decision

5. ERROR MONITORING
   - Track consecutive TMDB API errors
   - If ≥3: send Telegram admin alert

6. LOG COMPLETION
   - Write summary to logs/cron.log
```

**Estimated runtime:** For 500-title library:
- Step 1: ~20 watching series × 200ms = ~4 seconds
- Step 2: ~500 titles × 200ms = ~100 seconds
- Step 3 (Monday): ~500 titles × 400ms (2 calls) = ~200 seconds
- Total: ~2-5 minutes typical, ~7 minutes on Mondays

**Crontab entry:**
```bash
0 6 * * * cd /path/to/popcorn && /usr/bin/python3 cron/daily_check.py >> logs/cron.log 2>&1
```

---

## 17. Onboarding Guide Requirements

### Target Audience

Non-technical users who have never exported data from Netflix.

### Deliverables

Two files:
- `guides/netflix_export_guide_en.md` (English)
- `guides/netflix_export_guide_he.md` (Hebrew, RTL)

### Content Structure

```
Step 1: Open Netflix in your browser
  → Screenshot: browser address bar with netflix.com
  → Note: Must use browser, not the app

Step 2: Go to Account settings
  → Screenshot: Netflix menu → Account
  → Note: Click your profile icon in the top right

Step 3: Find your Profile
  → Screenshot: Profile & Parental Controls section
  → Note: Each profile has its own history — pick YOUR profile

Step 4: Click "Viewing Activity"
  → Screenshot: expanded profile section with Viewing Activity link

Step 5: Scroll to the bottom
  → Screenshot: bottom of page with "Download All" link highlighted

Step 6: Click "Download All"
  → Screenshot: browser download notification
  → Note: File will be named "NetflixViewingHistory.csv"

Step 7: Open Popcorn and upload
  → Screenshot: Popcorn upload area
  → Note: Click "Upload CSV" or drag the file into the box

Step 8: Wait for matching
  → Screenshot: progress bar
  → Note: This takes a few minutes for large histories

Step 9: Review flagged titles (if any)
  → Screenshot: review banner + review page
  → Note: The system wasn't sure about these — help it out!

Step 10: You're done!
  → Screenshot: populated dashboard
  → Note: Popcorn will check for new content daily. Enjoy! 🍿
```

### Critical Requirements

- Screenshots must be from the actual Netflix UI (taken during development)
- Each step must be ONE action only
- Language must be conversational, not technical
- Hebrew version must be fully localized (not Google Translated)
- File size under 5MB per guide (compressed screenshots)
- Must work on both desktop and mobile Netflix

---

## 18. Scope Boundaries

### ✅ In Scope for v0.1

1. Netflix Viewing Activity CSV import (Title + Date, 2-column format)
2. TMDB fuzzy matching with confidence scoring and review flow
3. Three-tab dashboard: Watch Next / Coming Soon / My Library
4. Manual content entry with TMDB autocomplete
5. New season detection via daily TMDB polling
6. Streaming availability in Israel via TMDB watch providers
7. Telegram push notifications (new seasons, recommendations, disambiguation)
8. Non-technical onboarding guide with screenshots (Hebrew + English)

### ❌ Out of Scope (Explicit Cuts with Rationale)

| Feature | Rationale (Principle) |
|---------|----------------------|
| Multi-user authentication | Single-user instance — "Ship the Toy" |
| Match confidence percentage in UI | Users need posters, not numbers — "One Screen, One Answer" |
| Dashboard filters / sort / search | Three tabs, scroll — "One Screen, One Answer" |
| Direct JustWatch API | TMDB already wraps it — "TMDB Is God" |
| Browser extension for other platforms | Manual entry covers this — "The CSV Is the Contract" |
| Telegram browsing / mini-app | Push only — "Telegram Is the Megaphone" |
| TV spin-off tracking | Sequels yes, spin-offs no — "Fuzzy Is Fine" |
| PostgreSQL / Redis / Docker | SQLite + single process — "Ship the Toy" |
| Real-time streaming updates | Daily is fine — "Stale Beats Silent" |
| Export/backup (beyond SQLite file copy) | Defer to v0.2 — "Ship the Toy" |
| CI/CD pipeline | `python app.py` is deployment — "Ship the Toy" |
| Mobile app | Web dashboard is mobile-responsive — "Ship the Toy" |
| Social features (sharing, ratings) | Personal tool — "Ship the Toy" |

---

## 19. Known Limitations & Accepted Risks

| # | Limitation | Impact | Mitigation |
|---|-----------|--------|------------|
| 1 | Netflix CSV has only Title + Date — no content type, no IDs | Entire accuracy depends on fuzzy string matching | Two-pass TMDB search + user review for low-confidence |
| 2 | Netflix logs every play attempt including 12-second accidental clicks | "Watched" list contains noise | User can manually remove entries from library |
| 3 | Netflix can remove CSV export feature at any time | Primary data input path breaks | Manual entry becomes sole input method |
| 4 | TMDB streaming data is 24-32h behind reality | "Now available" notifications are 1+ day late | Label as "updated daily" — users plan days ahead, not minutes |
| 5 | Israeli streaming coverage (HOT, YES, Partner TV) may be incomplete | Some local content shows no streaming source | Best-effort; validate coverage pre-launch |
| 6 | Hebrew title matching has edge cases (colons, inconsistent formatting) | ~10-20% of Hebrew titles may need manual correction | Flag for review at confidence < 0.6 |
| 7 | Series "watched" detection uses 80% episode threshold | Partially watched seasons may be misclassified | User can manually adjust status |
| 8 | No TV spin-off relationship tracking | Users won't be alerted about spin-off shows | Documented limitation; defer to v0.2 |
| 9 | Single-user, single-instance — no scaling path | Can't grow to multi-user without rewrite | Intentional — this is a personal toy |
| 10 | TMDB free tier prohibits commercial use | Can't monetize without TMDB commercial license | Acceptable for personal/community tool |

---

## 20. Decision Principles

### The 7 Guardrails

| # | Principle | One-Liner |
|---|-----------|-----------|
| 1 | **Fuzzy Is Fine** | 80% now beats 99% never. User corrects the rest. |
| 2 | **One Screen, One Answer** | If it needs a tutorial, it's too complex. |
| 3 | **Stale Beats Silent** | Yesterday's data > no data. Label honestly. |
| 4 | **The CSV Is the Contract** | Netflix CSV is the only automated input. Everything else is manual. |
| 5 | **Telegram Is the Megaphone** | Push notifications out. Don't build an app inside Telegram. |
| 6 | **TMDB Is God (For Now)** | Single source. No multi-API abstraction layers. |
| 7 | **Ship the Toy, Not the Platform** | SQLite. Single process. `python app.py`. Done. |

### Trade-Off Hierarchy

```
Ships fast        >  Ships right
Good enough       >  Perfectly accurate
Simple UX         >  Powerful UX
One API source    >  Multiple sources
Manual fallback   >  Automated fallback
Daily updates     >  Real-time updates
```

### Quick Decision Filter

```
1. Does a non-technical viewer NEED this?  NO → CUT
2. Can we ship without it?                 YES → DEFER
3. Does it add an API dependency?           YES → CUT
4. Can I explain it in one sentence?        NO → SIMPLIFY
```

---

## 21. Success Criteria

### Definition of Done (v0.1 Launch)

- [ ] Upload Netflix CSV → titles appear in "My Library" tab
- [ ] "Watch Next" tab shows recommendations with posters and streaming icons
- [ ] "Coming Soon" tab shows series with unwatched new seasons
- [ ] Streaming provider icons visible on title cards
- [ ] Telegram bot sends new season notification
- [ ] Telegram bot sends weekly recommendation digest
- [ ] Manual entry via autocomplete works end-to-end
- [ ] Low-confidence matches surfaced in review banner
- [ ] Daily cron runs without errors for 3 consecutive days
- [ ] Non-technical user completes onboarding guide without help
- [ ] TMDB attribution visible in dashboard footer
- [ ] `.env.example` documents all required environment variables
- [ ] README.md provides setup instructions

### Quantitative Targets

| Metric | Target |
|--------|--------|
| CSV import time (2000 entries) | < 10 minutes |
| Auto-match accuracy | ≥ 80% correct |
| Dashboard page load | < 2 seconds |
| Onboarding time (first-time user) | < 10 minutes |
| Daily cron runtime (500 titles) | < 10 minutes |
| New season notification latency | < 48h from TMDB update |

---

## 22. Implementation Plan

### Build Order (Sequential, No Skipping)

| Step | Component | Files | Hours | Dependencies |
|------|-----------|-------|-------|-------------|
| 1 | Database + Config | `db/schema.sql`, `config.py`, `.env.example` | 0.5 | None |
| 2 | CSV Parser | `ingestion/csv_parser.py`, `tests/test_csv_parser.py` | 1-2 | Step 1 |
| 3 | TMDB Matcher | `ingestion/tmdb_matcher.py`, `tests/test_tmdb_matcher.py` | 2-3 | Steps 1-2 |
| 4 | Engines | `engine/recommendations.py`, `engine/new_season_checker.py`, `engine/availability.py` | 3-4 | Steps 1-3 |
| 5 | Dashboard | `dashboard/app.py`, `templates/*`, `static/style.css` | 4-6 | Steps 1-4 |
| 6 | Telegram Bot | `bot/telegram_notifier.py` | 2-3 | Steps 1-4 |
| 7 | Cron + Guide | `cron/daily_check.py`, `guides/*` | 2 | Steps 1-6 |
| **Total** | | | **15-20** | |

### Pre-Flight Checklist

- [ ] Get TMDB API key: https://www.themoviedb.org/settings/api
- [ ] Create Telegram bot via @BotFather → save token
- [ ] Validate IL streaming coverage: query 20 titles via TMDB watch providers
- [ ] Export your own Netflix CSV and verify format
- [ ] Choose deployment target (VPS or local)

---

## 23. File Structure

```
popcorn/
├── README.md                          # Setup + usage instructions
├── CHANGELOG.md                       # v0.1 release notes
├── PRD.md                             # This document
├── .env.example                       # Template for secrets
├── .gitignore                         # .env, popcorn.db, logs/, *.csv
├── requirements.txt                   # Flask, requests, python-telegram-bot, python-dateutil
├── config.py                          # Load .env, define constants + thresholds
│
├── db/
│   └── schema.sql                     # SQLite DDL: all tables + indexes
│
├── ingestion/
│   ├── csv_parser.py                  # Netflix CSV → ParsedEntry list
│   └── tmdb_matcher.py                # ParsedEntry → MatchedTitle (TMDB fuzzy match)
│
├── engine/
│   ├── recommendations.py             # TMDB recommendations + collection sequels
│   ├── new_season_checker.py          # Compare watched seasons vs TMDB total
│   └── availability.py               # TMDB watch providers → IL availability
│
├── bot/
│   └── telegram_notifier.py           # Push notifications + inline keyboard callbacks
│
├── dashboard/
│   ├── app.py                         # Flask routes + logic
│   ├── templates/
│   │   ├── base.html                  # Layout shell with tabs + footer
│   │   ├── watch_next.html            # Recommendations tab
│   │   ├── coming_soon.html           # New seasons tab
│   │   ├── library.html               # Watch history tab
│   │   └── review.html               # Low-confidence match review
│   └── static/
│       └── style.css                  # Minimal custom styles (Pico CSS base)
│
├── cron/
│   └── daily_check.py                 # Orchestrator: seasons + availability + recs + alerts
│
├── guides/
│   ├── netflix_export_guide_en.md     # English onboarding with screenshots
│   └── netflix_export_guide_he.md     # Hebrew onboarding with screenshots
│
├── tests/
│   ├── test_csv_parser.py             # Edge cases: Hebrew, colons, dates, empty rows
│   ├── test_tmdb_matcher.py           # Ambiguous titles, series vs movie, no-match
│   └── test_recommendations.py        # New season detection, collection lookup
│
└── logs/
    └── .gitkeep                       # Cron log output directory
```

---

## 24. Dependencies

### requirements.txt

```
flask>=3.0
requests>=2.31
python-telegram-bot>=20.0
python-dateutil>=2.8
```

**That's it.** SQLite is built into Python. No ORM. No Redis. No Celery. No Docker.

### System Requirements

- Python 3.11+
- System crontab (any Linux/macOS)
- Internet access (TMDB API + Telegram API)
- ~100MB disk space (SQLite DB + posters are served from TMDB CDN, not stored locally)

---

## 25. Future Considerations (v0.2+)

These are explicitly NOT in v0.1. Listed here for context only — to prevent re-discussion.

| Feature | When to Consider | Trigger |
|---------|-----------------|---------|
| Multi-user support | If 3+ people want their own instance | Demand, not speculation |
| PostgreSQL migration | If SQLite hits performance wall | Measurable slowness, not theoretical concern |
| Dashboard filters/search | If library exceeds 500 titles and scrolling is painful | User feedback |
| TV spin-off tracking | When TMDB improves franchise data | TMDB API change |
| Export/import user data | When first user asks for it | User request |
| Mobile app | If web dashboard proves insufficient on phones | Measurable UX gap |
| Integration with Trakt/Letterboxd | If user wants cross-platform history | User request |
| Collaborative features (friend recs) | If friend group actively wants shared lists | Social demand |
| Real-time availability checks | If "just released" latency matters to users | User complaint |
| CI/CD pipeline | If deployment becomes error-prone | Operational pain |
| Docker containerization | If deploying on new machines frequently | Operational need |
| Custom recommendation algorithm | If TMDB recommendations feel irrelevant | Quality feedback |

---

## Appendix A: TMDB API Quick Reference

### Authentication

```
Header: Authorization: Bearer {TMDB_API_KEY}
```

### Key Endpoints Used

```
Search:
  GET /search/movie?query={q}&language={lang}
  GET /search/tv?query={q}&language={lang}
  GET /search/multi?query={q}&language={lang}

Details:
  GET /movie/{id}?language={lang}
  GET /tv/{id}?language={lang}

Recommendations:
  GET /movie/{id}/recommendations?language={lang}
  GET /tv/{id}/recommendations?language={lang}

Collections:
  GET /collection/{id}?language={lang}

Watch Providers:
  GET /movie/{id}/watch/providers
  GET /tv/{id}/watch/providers

Images:
  Poster: https://image.tmdb.org/t/p/w200{poster_path}
  Provider logo: https://image.tmdb.org/t/p/original{logo_path}
```

### Response Handling

- Empty results → move to next search pass
- 429 (rate limited) → back off 1 second, retry once
- 5xx → log error, increment error counter, continue to next title
- No `IL` key in watch providers → title has no Israeli streaming availability

---

## Appendix B: Netflix CSV Parsing Reference

### Known Title Formats

```
Movie (simple):          "Inception"
Movie (with colon):      "Mission: Impossible - Fallout"
Series (English):        "Breaking Bad: Season 1: Pilot"
Series (Hebrew):         "הכלה מאיסטנבול: עונה 1: פרק 3"
Series (German):         "Dark: Staffel 2: Episode 5"
Series (no season num):  "Black Mirror: Bandersnatch"
Series (Part format):    "Money Heist: Part 3: Episode 1"
Empty/malformed:         "" or malformed rows → skip
```

### Season Detection Patterns

```python
SEASON_PATTERNS = [
    r'Season\s+(\d+)',      # English
    r'Part\s+(\d+)',        # English alternate
    r'עונה\s+(\d+)',        # Hebrew
    r'Staffel\s+(\d+)',     # German
    r'Saison\s+(\d+)',      # French
    r'Temporada\s+(\d+)',   # Spanish
]
```

### Date Format Handling

```python
from dateutil.parser import parse
date = parse(date_string, dayfirst=True)  # Handles MM/DD/YY and DD/MM/YY
```

---

*This PRD is the single comprehensive reference for Popcorn v0.1. All other documents (Vision, Architecture, Implementation Instructions, Philosophical Grounding, Executive Summary) are subsets of this document optimized for specific audiences and use cases.*

*Built with Grounded Progressive Architecture (GPA) methodology.*
