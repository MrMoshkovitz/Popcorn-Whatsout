# 🍿 Popcorn — Philosophical Grounding

**The "Why" Behind Every Decision**

---

## Core Philosophy: "Couch Potato Sovereignty"

The system serves the viewer's laziness with dignity. It suggests, never nags. It guesses smart, never forces precision. It embraces "good enough" over "perfectly accurate."

This philosophy is the decision filter for every feature, scope question, and technical tradeoff in Popcorn.

---

## The 7 Decision Principles

### 1. "Fuzzy Is Fine"

**Statement:** 80% accurate matching that works NOW beats 99% matching that ships never. If the system guesses wrong on 1 in 10 titles — that's acceptable. The user can correct manually.

**Applied to:**
- TMDB title matching uses first result by popularity, not ML-powered disambiguation
- Confidence threshold auto-accepts above 0.6, flags below for manual review
- Series vs. movie detection uses simple colon-split heuristic, not NLP
- Hebrew title matching does two-pass search (he-IL → en-US) with no transliteration engine

**Temptation resisted:** Building an elaborate NLP pipeline for title disambiguation. Spending weeks on Hebrew regex edge cases. Adding Levenshtein distance algorithms. Integrating multiple metadata sources for cross-validation.

---

### 2. "One Screen, One Answer"

**Statement:** A non-technical user should never need to make more than one decision per screen. No compound filters. No "advanced mode." If it needs a tutorial, it's too complex.

**Applied to:**
- Dashboard has three tabs, zero filters — just scroll
- No match percentage displayed (users don't need numbers, they need posters)
- Manual entry is one search bar with autocomplete — pick from 5 results, done
- Low-confidence review is a simple "correct" / "search again" binary choice

**Temptation resisted:** Adding sort-by-match-percentage + filter-by-platform + filter-by-status + search all visible simultaneously. Dashboard feature creep disguised as "user options." Settings pages. Preference panels.

---

### 3. "Stale Beats Silent"

**Statement:** Showing yesterday's streaming availability is infinitely better than showing nothing. Data staleness (24-32h) is a known, accepted tradeoff — not a bug to fix. Label it honestly: "Updated daily."

**Applied to:**
- TMDB watch provider data is 24-32h behind JustWatch — accepted, labeled
- Daily cron is sufficient; no real-time webhooks or polling
- Recommendations update weekly (Mondays), not on every page load
- New season checks happen once daily at 6 AM, not on user request

**Temptation resisted:** Building real-time streaming checks. Chasing JustWatch Partner API access. Over-engineering polling frequency. Adding "refresh now" buttons that hammer APIs.

---

### 4. "The CSV Is the Contract"

**Statement:** The Netflix CSV is the ONLY automated input. Everything else (other platforms, corrections, manual adds) is manual-by-design. Don't build scrapers or integrations for platforms that don't hand you data freely.

**Applied to:**
- Only the Netflix Viewing Activity CSV is supported for import
- All other content (Disney+, Apple TV, cinema visits) → manual entry
- No browser extension, no screen scraping, no API hacks for other platforms
- If Netflix removes the CSV export → manual entry becomes the only path

**Temptation resisted:** Building browser extensions to scrape Disney+/Apple TV. Trying to auto-detect viewing history from other sources. Expanding the input surface beyond what's given for free. Building an "import from Letterboxd/Trakt" feature.

---

### 5. "Telegram Is the Megaphone, Not the App"

**Statement:** Telegram sends notifications OUT. It does NOT replace the dashboard. Two-way interaction is limited to simple yes/no disambiguation — not browsing, filtering, or managing a watchlist.

**Applied to:**
- Telegram is push-only: new seasons, new recommendations, disambiguation
- No `/commands` for browsing or searching
- No conversational flows beyond inline keyboard responses
- 48h timeout on disambiguation → auto-pick, don't wait forever

**Temptation resisted:** Building a full Telegram mini-app with inline keyboards for browsing recommendations. Replicating the dashboard inside Telegram. Adding conversation flows with stateful sessions. Building a Telegram-first experience.

---

### 6. "TMDB Is God (For Now)"

**Statement:** TMDB is the single source for metadata, recommendations, and streaming availability. Don't multi-source. Don't build fallbacks to OMDB/Trakt/Watchmode. If TMDB doesn't have it, it doesn't exist in Popcorn v0.1.

**Applied to:**
- All metadata comes from TMDB (titles, posters, genres, collections)
- Recommendations use TMDB's `/recommendations` endpoint only
- Streaming availability uses TMDB's watch providers (JustWatch data) only
- Hebrew support leverages TMDB's native `language=he-IL` parameter

**Temptation resisted:** Adding OMDB as fallback for failed matches. Cross-referencing Trakt for better recommendations. Building an abstraction layer "in case we switch providers later." Using Watchmode API for streaming data.

---

### 7. "Ship the Toy, Not the Platform"

**Statement:** Popcorn v0.1 is a personal toy for ONE user with ONE Netflix profile. No multi-user auth. No user management. No scaling concerns. Deploy it on a single VPS with SQLite if that's fastest.

**Applied to:**
- SQLite, not PostgreSQL/MySQL
- Single Python process, not microservices
- No Docker, no Kubernetes, no CI/CD
- No authentication, no sessions, no user registration
- No rate limiting beyond basic upload throttle
- `python app.py` is the deployment strategy

**Temptation resisted:** PostgreSQL cluster setup. Redis caching layer. User registration flow. OAuth. Docker compose with 5 services. GitHub Actions pipeline. "But what if we need to scale?" — we don't.

---

## The Decision Filter (Quick Reference)

For every "should we add X?" question:

```
┌─ Does a non-technical viewer need this to enjoy Popcorn?
│   NO → CUT
│   YES ↓
├─ Can we ship without it and add it later?
│   YES → DEFER
│   NO ↓
├─ Does it require a new API dependency?
│   YES → CUT (unless no alternative exists)
│   NO ↓
├─ Can I explain this to my mom in one sentence?
│   NO → SIMPLIFY
│   YES → BUILD IT
└─────────────────────────────────────
```

## Trade-Off Hierarchy

When principles conflict, apply this priority order:

```
1. Ships fast        >  Ships right
2. Good enough       >  Perfectly accurate
3. Simple UX         >  Powerful UX
4. One API source    >  Multiple sources
5. Manual fallback   >  Automated fallback
6. Daily updates     >  Real-time updates
7. SQLite            >  "Proper" database
```

---

## Decisions Log: Phase 3 Problems → Phase 5 Resolutions

Every Phase 3 problem was resolved using these principles. Full mapping:

| Problem | Principle Applied | Decision |
|---------|------------------|----------|
| CSV has only Title + Date | Fuzzy Is Fine | Accept. Fuzzy match is the whole strategy. |
| Title parsing regex | Fuzzy Is Fine | Simple colon-split. TMDB corrects misparses. |
| Date locale variance | Ship the Toy | `dateutil.parser.parse(dayfirst=True)`. One line. |
| Partial views logged | Couch Potato Sovereignty | Accept. User can manually remove. |
| Per-profile CSV | Ship the Toy | One profile per instance. |
| GDPR vs Viewing Activity | One Screen, One Answer | Viewing Activity only (instant, simple). |
| Ambiguous matches | Fuzzy Is Fine | TMDB result #1 by popularity. Flag low confidence. |
| Hebrew titles | TMDB Is God | Two-pass search: he-IL → en-US. |
| Series vs movie | Fuzzy Is Fine | Colon heuristic + TMDB fallback. |
| 6000+ API calls on import | Ship the Toy | Deduplicate titles first. 200ms delay. Progress bar. |
| Similar vs Recommendations | TMDB Is God | Use `/recommendations` + `/collection`. |
| Daily polling 100+ series | Stale Beats Silent | Only poll `status=watching` series. Cache 24h. |
| Spin-off relationships | Fuzzy Is Fine | Defer. Sequels yes, spin-offs no. |
| Thin Israeli content data | TMDB Is God | Accept. Manual entry fills gaps. |
| JustWatch no public API | TMDB Is God | Use TMDB watch providers endpoint (wraps JustWatch). |
| 24-32h staleness | Stale Beats Silent | Label "updated daily." No fix needed. |
| Israeli streaming coverage | Ship the Toy | Validate pre-launch. Best-effort if thin. |
| Catalogs change constantly | Stale Beats Silent | Daily polling updates availability. |
| No Telegram delivery guarantee | Telegram Is Megaphone | Accept. Dashboard is source of truth. |
| Stale disambiguation | Fuzzy Is Fine | 48h timeout → auto-pick highest popularity. |
| Limited Telegram formatting | Telegram Is Megaphone | Text + inline keyboard + poster. Enough. |
| Bot command discoverability | One Screen, One Answer | No commands. Push-only. Zero learning curve. |
| Simplicity vs functionality | One Screen, One Answer | Three tabs, no filters, just scroll. |
| Autocomplete API calls | Ship the Toy | Standard debounce 300ms. |
| Hebrew RTL + English LTR | Fuzzy Is Fine | `dir="auto"`. Let browser handle BiDi. |
| Match level explainability | One Screen, One Answer | Cut. No percentages. Just show posters. |
| Series "watched" threshold | Fuzzy Is Fine | ≥80% episodes = watched. Simple count. |
| CSV re-import merge | Couch Potato Sovereignty | Upsert. Manual entries never overwritten. |
| No backup/export | Ship the Toy | SQLite file IS the backup. Defer proper export. |
| TMDB attribution | Non-negotiable | Footer with logo + disclaimer. |
| Netflix kills CSV | The CSV Is the Contract | Accepted risk. Manual entry is fallback. |
| No network effects | Ship the Toy | TMDB's data IS the network effect. |
| No monitoring | Ship the Toy | Log to file. 3 consecutive errors → Telegram alert. |
| CSV reveals habits | Minimal hygiene | Delete CSV after processing. Store only TMDB IDs. |
| Bot token exposure | Non-negotiable | `.env` file. `.gitignore`. |
| No upload rate limiting | Ship the Toy | One upload per 24h. Timestamp check. |

---

## Philosophy Origin

This grounding follows the GPA (Grounded Progressive Architecture) methodology:

- **Phase 1** gave us the concrete vision (Netflix CSV → recommendations)
- **Phase 2** deepened it (TMDB matching, streaming availability, Telegram)
- **Phase 3** flooded 36 problems without fixing them
- **Phase 4** established these 7 principles to filter all decisions
- **Phase 5** applied principles to resolve every problem decisively

The philosophy is not decorative. It's the operating system for every future decision about Popcorn.

---

*When in doubt, ask: "Would this feel like Popcorn, or like enterprise software?"*
*If the answer is enterprise — cut it.*
