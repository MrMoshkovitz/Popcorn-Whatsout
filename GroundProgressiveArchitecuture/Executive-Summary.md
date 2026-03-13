# 🍿 Popcorn — Executive Summary

**Version:** v0.1 Planning Complete
**Date:** March 2026
**Status:** Architecture locked. Ready for implementation.

---

## What Is Popcorn?

A personal smart tracking and recommendation system for movies and TV shows. Upload your Netflix viewing history CSV → get matched to TMDB → receive recommendations, new season alerts, and streaming availability — all through a simple dashboard and Telegram notifications.

## Core User Promise

**"Never miss a sequel, new season, or great recommendation — without lifting a finger after the first upload."**

## Target User

One non-technical person (or small friend group) who watches Netflix and wants to know:
1. What should I watch next? (recommendations)
2. Did that show I liked get a new season? (new season detection)
3. Where can I watch it? (streaming availability in Israel)

## Minimal Viable Interaction Loop

```
1. User exports Netflix CSV (guided by screenshot-based guide)
2. User uploads CSV to Popcorn dashboard
3. System fuzzy-matches titles to TMDB
4. Dashboard shows: "Watch Next" / "Coming Soon" / "My Library"
5. Daily cron checks for new seasons + availability changes
6. Telegram bot pushes notifications for new content
7. User can manually add non-Netflix content via autocomplete
```

## Strategic Name: "Popcorn"

Anchors AI and developers to the core experience: casual, fun, zero-effort entertainment tracking. Not a "media management platform" — a couch companion.

## Philosophy: "Couch Potato Sovereignty"

The system serves the viewer's laziness with dignity. It suggests, never nags. It guesses smart, never forces precision. It embraces "good enough" over "perfectly accurate."

## Key Technical Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Data source | Netflix CSV (Viewing Activity) | Free, instant, no auth needed |
| Metadata API | TMDB (single source) | Free, generous limits, Hebrew support, includes JustWatch data |
| Streaming availability | TMDB watch providers (IL region) | No direct JustWatch dependency needed |
| Database | SQLite | Single-user tool, zero ops overhead |
| Notifications | Telegram Bot (push-only) | No app to build, instant reach |
| Dashboard | Minimal web app (Flask/FastAPI) | Three tabs, no filters, scroll-based |

## Scope Summary

**IN:** CSV import, TMDB matching, 3-tab dashboard, manual entry, new season detection, streaming availability (IL), Telegram push, onboarding guide

**OUT:** Multi-user auth, match percentages, Telegram mini-app, browser extensions, PostgreSQL/Redis/Docker, TV spin-off tracking, dashboard filters

## Risk Acknowledgments

1. Netflix can remove CSV export anytime — manual entry is the fallback
2. TMDB community data is thin for Israeli niche content
3. Streaming availability has 24-32h staleness — labeled "updated daily"
4. Fuzzy title matching will have ~10-20% error rate — user can correct manually

## GPA Process Used

| Phase | Output |
|-------|--------|
| P1: Vision Casting | Core concept + strategic naming |
| P2: Iterative Deepening | Refined 14-point feature spec with expected challenges |
| P3: Stress Testing | 36 problems identified across 9 categories |
| P4: Philosophical Grounding | 7 decision principles + trade-off hierarchy |
| P5: Boundary Setting | Every problem resolved with principle-backed decision |
| P6: This document set | Single Source of Truth for implementation |

---

*Built with Grounded Progressive Architecture (GPA) methodology.*
