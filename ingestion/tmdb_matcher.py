import logging
import sqlite3
from difflib import SequenceMatcher

from config import MATCH_CONFIDENCE_THRESHOLD, DB_PATH
from ingestion.tmdb_api import two_pass_search_with_type_fallback, tmdb_get

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
    }


def match_entries(entries: list[dict], conn: sqlite3.Connection, user_tag: str = 'both') -> dict:
    """Match parsed entries to TMDB. Returns stats dict {matched, review, errors}."""
    stats = {"matched": 0, "review": 0, "errors": 0}

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
            }
            stats["errors"] += 1

    cursor = conn.cursor()

    # Step 3: Upsert matched titles into titles table
    title_id_lookup = {}
    for name, match in matches.items():
        if match["tmdb_id"] is None:
            stats["review"] += 1
            continue

        cursor.execute(
            """INSERT OR REPLACE INTO titles
               (tmdb_id, tmdb_type, title_en, title_he, poster_path, original_language, confidence, match_status, source, user_tag)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'csv', ?)""",
            (match["tmdb_id"], match["tmdb_type"], match["title_en"],
             match["title_he"], match["poster_path"], match.get("original_language"),
             match["confidence"], match["match_status"], user_tag),
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

    # Step 4: Insert all entries into watch_history
    for entry in entries:
        name = entry["parsed_name"]
        title_id = title_id_lookup.get(name)
        if title_id is None:
            continue

        try:
            cursor.execute(
                """INSERT OR REPLACE INTO watch_history
                   (title_id, raw_csv_title, watch_date, season_number, episode_name)
                   VALUES (?, ?, ?, ?, ?)""",
                (title_id, entry["title"], entry["watch_date"],
                 entry.get("season_number"), entry.get("episode_name")),
            )
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

        cursor.execute(
            """INSERT OR IGNORE INTO series_tracking
               (title_id, tmdb_id, total_seasons_tmdb, max_watched_season,
                next_season_air_date, total_episodes_tmdb, status)
               VALUES (?, ?, ?, ?, ?, ?, 'watching')""",
            (title_id, match["tmdb_id"], total_seasons, max_season,
             next_air_date, total_episodes),
        )

    # Step 6: Commit once
    conn.commit()

    return stats
