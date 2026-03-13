# 🍿 Popcorn — Vision

**The North Star Document**

---

## One-Line Vision

A personal movie & TV tracking system that turns your Netflix history into smart recommendations, new-season alerts, and "where to watch" answers — with zero ongoing effort.

---

## The Problem

You finish binge-watching a great series. Six months later, a new season drops — and you miss it entirely. A sequel to a movie you loved comes out — you find out a year late. You want something similar to watch tonight — but scrolling Netflix for 20 minutes yields nothing.

Meanwhile, your Netflix viewing history sits there with years of data about your taste, doing absolutely nothing for you.

## The Solution: Popcorn

Upload your Netflix CSV once. Popcorn does the rest:

1. **Matches** every title to TMDB's database (fuzzy, automatic, good-enough)
2. **Recommends** similar content based on what you've actually watched
3. **Tracks** every series you've started and alerts you when new seasons drop
4. **Shows** where each title is available to stream in Israel
5. **Notifies** you via Telegram when something new appears

## Who Is This For?

- **Primary:** One non-technical person who watches Netflix regularly
- **Secondary:** A small group of friends sharing recommendations
- **NOT for:** Power users who want Letterboxd/Trakt-level customization

## Core Interaction Model

```
INPUT:
  → Netflix Viewing Activity CSV (one-time upload)
  → Manual entries for non-Netflix content (optional)

PROCESSING:
  → Title string → TMDB fuzzy match → Store TMDB ID + metadata
  → Daily cron: check for new seasons, availability changes

OUTPUT:
  → Dashboard: "Watch Next" / "Coming Soon" / "My Library"
  → Telegram: push notifications for new content
```

## What Popcorn Is NOT

- Not a social platform (no friends, no sharing, no likes)
- Not a universal media tracker (Netflix CSV + manual only)
- Not a precision tool (fuzzy matching is a feature, not a bug)
- Not a real-time system (daily updates are by design)
- Not a Telegram app (Telegram is the megaphone, not the interface)

## Success Criteria for v0.1

1. A non-technical user can go from zero to working dashboard in under 10 minutes
2. 80%+ of Netflix titles match correctly to TMDB without user intervention
3. New season notifications arrive within 48 hours of a new season appearing on TMDB
4. The dashboard loads and is immediately understandable without any tutorial
5. Total infrastructure: one VPS, one SQLite file, one Python process

## The Name: Popcorn

Casual. Fun. Zero pretension. It anchors every decision to the couch experience — not to "media management" or "content intelligence." When in doubt about a feature: "Would this feel like Popcorn, or like enterprise software?"

---

## Data Flow Overview

```
Netflix CSV                TMDB API
    │                        │
    ▼                        ▼
┌──────────┐         ┌─────────────┐
│ CSV      │────────▶│ Matcher     │
│ Parser   │         │ (fuzzy)     │
└──────────┘         └──────┬──────┘
                            │
                            ▼
                     ┌─────────────┐
                     │  SQLite DB  │
                     │  (titles,   │
                     │  episodes,  │
                     │  recs)      │
                     └──────┬──────┘
                            │
                ┌───────────┼───────────┐
                ▼           ▼           ▼
          ┌──────────┐ ┌────────┐ ┌──────────┐
          │Dashboard │ │  Cron  │ │ Telegram │
          │ (3 tabs) │ │(daily) │ │  (push)  │
          └──────────┘ └────────┘ └──────────┘
```

## API Dependencies

| API | Usage | Rate Limit | Cost | Risk |
|-----|-------|-----------|------|------|
| TMDB | Metadata, search, recommendations, watch providers | ~50 req/sec (CDN) | Free (non-commercial, with attribution) | Community-edited data, thin coverage for niche Israeli content |
| Telegram Bot API | Push notifications, inline keyboard for disambiguation | 30 msg/sec | Free | No delivery guarantee for offline users |
| Netflix CSV | Viewing history input | N/A (file upload) | Free | Netflix can change/remove export anytime |

## Key Constraints (Accepted)

- Netflix CSV = Title + Date only (no genre, no IDs, no watch percentage)
- TMDB streaming data = 24-32h stale (via JustWatch daily export)
- Fuzzy matching = ~80-90% accuracy (user corrects the rest)
- Single user per instance (no auth, no multi-tenancy)
- Hebrew + English mixed content (BiDi handled via `dir="auto"`)

---

*This is the north star. Every implementation decision must trace back to this document.*
