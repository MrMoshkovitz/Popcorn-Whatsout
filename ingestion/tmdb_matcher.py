import json
import logging
import sqlite3
from difflib import SequenceMatcher

from config import MATCH_CONFIDENCE_THRESHOLD, DB_PATH
from ingestion.tmdb_api import two_pass_search_with_type_fallback, tmdb_get
from engine.genre_map import get_genre_names

logger = logging.getLogger(__name__)


def calculate_confidence(query: str, result: dict) -> float:
    """Score 0.0-1.0: name similarity (70%) + popularity (30%, capped at 100)."""
    result_title = result.get("title") or result.get("name") or ""
    name_ratio = SequenceMatcher(None, query.lower(), result_title.lower()).ratio()
    popularity = result.get("popularity", 0)
    popularity_factor = min(popularity / 100, 1.0)
    confidence = (name_ratio * 0.7) + (popularity_factor * 0.3)
    return round(confidence, 4)


def _build_matched_title(parsed_name: str, result: dict, media_type: str) -> dict:
    """Build a MatchedTitle dict from a TMDB search result."""
    confidence = calculate_confidence(parsed_name, result)
    match_status = "auto" if confidence >= MATCH_CONFIDENCE_THRESHOLD else "review"

    # From he-IL search: "title"/"name" = Hebrew localized, "original_title"/"original_name" = original language
    if media_type == "movie":
        title_he = result.get("title")
    else:
        title_he = result.get("name")

    title_en = result.get("original_title") or result.get("original_name")

    genre_ids = result.get("genre_ids", [])
    genre_names = get_genre_names(genre_ids, media_type)

    release_date = result.get("release_date") or result.get("first_air_date") or ""
    release_year = release_date[:4] if release_date else None

    return {
        "parsed_name": parsed_name,
        "tmdb_id": result.get("id"),
        "tmdb_type": media_type,
        "title_he": title_he,
        "title_en": title_en,
        "original_language": result.get("original_language"),
        "confidence": confidence,
        "match_status": match_status,
        "poster_path": result.get("poster_path"),
        "genres": json.dumps(genre_names) if genre_names else None,
        "overview": result.get("overview"),
        "backdrop_path": result.get("backdrop_path"),
        "vote_average": result.get("vote_average"),
        "release_year": release_year,
    }


def _match_single(parsed_name: str, media_type_hint: str) -> dict:
    """Match a single parsed name to TMDB using two-pass search with type fallback."""
    result, actual_type = two_pass_search_with_type_fallback(parsed_name, media_type_hint)

    if result:
        return _build_matched_title(parsed_name, result, actual_type)

    return {
        "parsed_name": parsed_name,
        "tmdb_id": None,
        "tmdb_type": media_type_hint,
        "title_he": None,
        "title_en": None,
        "original_language": None,
        "confidence": 0.0,
        "match_status": "review",
        "poster_path": None,
        "genres": None,
        "overview": None,
        "backdrop_path": None,
        "vote_average": None,
        "release_year": None,
    }


def match_entries(entries: list[dict], conn: sqlite3.Connection, user_tag: str = 'both') -> dict:
    """Match parsed entries to TMDB. Returns stats dict {matched, review, errors}."""
    stats = {"matched": 0, "review": 0, "errors": 0, "skipped": 0, "new_episodes": 0}

    if not entries:
        return stats

    # Step 1: Deduplicate by parsed_name
    unique_entries = {}
    for entry in entries:
        name = entry["parsed_name"]
        if name not in unique_entries:
            unique_entries[name] = entry

    # Step 2: Match each unique name
    matches = {}
    for name, entry in unique_entries.items():
        try:
            match = _match_single(name, entry["media_type_hint"])
            matches[name] = match
        except Exception as e:
            logger.warning(f"Failed to match '{name}': {e}")
            matches[name] = {
                "parsed_name": name,
                "tmdb_id": None,
                "tmdb_type": entry["media_type_hint"],
                "title_he": None,
                "title_en": None,
                "original_language": None,
                "confidence": 0.0,
                "match_status": "review",
                "poster_path": None,
                "genres": None,
                "overview": None,
                "backdrop_path": None,
                "vote_average": None,
                "release_year": None,
            }
            stats["errors"] += 1

    cursor = conn.cursor()

    # Step 3: Insert new titles, skip existing ones to preserve manual edits
    title_id_lookup = {}
    for name, match in matches.items():
        if match["tmdb_id"] is None:
            stats["review"] += 1
            continue

        # Check if title already exists
        existing = cursor.execute(
            "SELECT id, match_status, user_tag FROM titles WHERE tmdb_id = ? AND tmdb_type = ?",
            (match["tmdb_id"], match["tmdb_type"]),
        ).fetchone()

        if existing:
            title_id_lookup[name] = existing[0] if not isinstance(existing, sqlite3.Row) else existing["id"]
            stats["skipped"] += 1
            continue

        # Insert new title (not INSERT OR REPLACE)
        cursor.execute(
            """INSERT INTO titles
               (tmdb_id, tmdb_type, title_en, title_he, poster_path, original_language,
                confidence, match_status, source, user_tag, genres,
                overview, backdrop_path, vote_average, release_year)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'csv', ?, ?, ?, ?, ?, ?)""",
            (match["tmdb_id"], match["tmdb_type"], match["title_en"],
             match["title_he"], match["poster_path"], match.get("original_language"),
             match["confidence"], match["match_status"], user_tag, match.get("genres"),
             match.get("overview"), match.get("backdrop_path"),
             match.get("vote_average"), match.get("release_year")),
        )

        # Get the title_id
        cursor.execute(
            "SELECT id FROM titles WHERE tmdb_id = ? AND tmdb_type = ?",
            (match["tmdb_id"], match["tmdb_type"]),
        )
        row = cursor.fetchone()
        if row:
            title_id_lookup[name] = row["id"] if isinstance(row, sqlite3.Row) else row[0]

        if match["match_status"] == "auto":
            stats["matched"] += 1
        else:
            stats["review"] += 1

    # Step 4: Insert new watch_history entries (IGNORE duplicates)
    for entry in entries:
        name = entry["parsed_name"]
        title_id = title_id_lookup.get(name)
        if title_id is None:
            continue

        try:
            cursor.execute(
                """INSERT OR IGNORE INTO watch_history
                   (title_id, raw_csv_title, watch_date, season_number, episode_name)
                   VALUES (?, ?, ?, ?, ?)""",
                (title_id, entry["title"], entry["watch_date"],
                 entry.get("season_number"), entry.get("episode_name")),
            )
            if cursor.rowcount > 0:
                stats["new_episodes"] += 1
        except Exception as e:
            logger.warning(f"Failed to insert watch_history for '{name}': {e}")

    # Step 5: Populate series_tracking for TV shows
    for name, match in matches.items():
        if match["tmdb_type"] != "tv" or match["tmdb_id"] is None:
            continue

        title_id = title_id_lookup.get(name)
        if title_id is None:
            continue

        # Find max watched season from entries
        max_season = None
        for entry in entries:
            if entry["parsed_name"] == name and entry.get("season_number") is not None:
                if max_season is None or entry["season_number"] > max_season:
                    max_season = entry["season_number"]

        # Fetch total seasons from TMDB
        total_seasons = None
        total_episodes = None
        next_air_date = None
        detail = tmdb_get(f"/tv/{match['tmdb_id']}", {"language": "en-US"})
        if detail:
            total_seasons = detail.get("number_of_seasons")
            total_episodes = detail.get("number_of_episodes")
            next_season = (max_season or 0) + 1
            if next_season <= (total_seasons or 0):
                for s in detail.get("seasons", []):
                    if s.get("season_number") == next_season:
                        next_air_date = s.get("air_date")
                        break

        existing_tracking = cursor.execute(
            "SELECT max_watched_season FROM series_tracking WHERE title_id = ?",
            (title_id,)
        ).fetchone()

        if existing_tracking:
            # Update only if CSV shows a higher season
            existing_max = existing_tracking[0] if not isinstance(existing_tracking, sqlite3.Row) else existing_tracking["max_watched_season"]
            if max_season and (existing_max is None or max_season > existing_max):
                cursor.execute(
                    "UPDATE series_tracking SET max_watched_season = ?, total_seasons_tmdb = ?, "
                    "next_season_air_date = ?, total_episodes_tmdb = ? WHERE title_id = ?",
                    (max_season, total_seasons, next_air_date, total_episodes, title_id),
                )
        else:
            cursor.execute(
                """INSERT INTO series_tracking
                   (title_id, tmdb_id, total_seasons_tmdb, max_watched_season,
                    next_season_air_date, total_episodes_tmdb, status)
                   VALUES (?, ?, ?, ?, ?, ?, 'watching')""",
                (title_id, match["tmdb_id"], total_seasons, max_season,
                 next_air_date, total_episodes),
            )

    # Step 6: Commit once
    conn.commit()

    return stats
