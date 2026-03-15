"""Franchise/collection tracker for movies.

Detects movie collections via TMDB belongs_to_collection,
tracks unreleased parts for Coming Soon display.
"""

import logging
from datetime import datetime, timedelta

import dateutil.parser

from ingestion.tmdb_api import tmdb_get
from config import TMDB_LANGUAGE_PRIMARY

logger = logging.getLogger(__name__)

CHECK_INTERVAL_HOURS = 24


def check_franchises(conn) -> list[dict]:
    """Check all movies for collection membership, track unreleased parts.

    Returns list of alert dicts for newly discovered unreleased movies.
    """
    cursor = conn.execute(
        "SELECT id, tmdb_id FROM titles WHERE tmdb_type = 'movie'"
    )
    movies = cursor.fetchall()
    logger.info(f"Checking {len(movies)} movies for franchise membership")

    # Group movies by collection to avoid redundant API calls
    collection_sources = {}  # collection_id -> list of title ids
    collection_meta = {}     # collection_id -> collection basic info

    for movie in movies:
        movie_data = tmdb_get(f"/movie/{movie['tmdb_id']}", {"language": TMDB_LANGUAGE_PRIMARY})
        if not movie_data:
            continue
        collection = movie_data.get("belongs_to_collection")
        if not collection:
            continue
        coll_id = collection["id"]
        if coll_id not in collection_sources:
            collection_sources[coll_id] = []
            collection_meta[coll_id] = collection
        collection_sources[coll_id].append(movie["id"])

    alerts = []
    checked = 0
    skipped = 0

    for coll_id, source_ids in collection_sources.items():
        # Check if recently checked
        existing = conn.execute(
            "SELECT last_checked FROM franchise_tracking WHERE collection_id = ?",
            (coll_id,)
        ).fetchone()
        if existing and existing["last_checked"]:
            try:
                last_dt = dateutil.parser.parse(existing["last_checked"])
                if datetime.utcnow() - last_dt < timedelta(hours=CHECK_INTERVAL_HOURS):
                    skipped += 1
                    continue
            except (ValueError, TypeError):
                pass

        # Fetch full collection data
        coll_data = tmdb_get(f"/collection/{coll_id}", {"language": TMDB_LANGUAGE_PRIMARY})
        if not coll_data:
            continue

        parts = coll_data.get("parts", [])
        total_parts = len(parts)
        coll_name = coll_data.get("name") or collection_meta[coll_id].get("name")

        # Count watched parts (those in our titles + watch_history)
        watched_count = 0
        watched_tmdb_ids = set()
        for part in parts:
            row = conn.execute(
                "SELECT t.id FROM titles t "
                "JOIN watch_history wh ON t.id = wh.title_id "
                "WHERE t.tmdb_id = ? AND t.tmdb_type = 'movie'",
                (part["id"],)
            ).fetchone()
            if row:
                watched_count += 1
                watched_tmdb_ids.add(part["id"])

        # Find next unreleased part
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        next_unreleased = None
        for part in sorted(parts, key=lambda p: p.get("release_date") or "9999-12-31"):
            if part["id"] in watched_tmdb_ids:
                continue
            release_date = part.get("release_date")
            if not release_date or release_date > today_str:
                next_unreleased = part
                break

        # Upsert franchise_tracking
        source_ids_str = ",".join(str(sid) for sid in source_ids)
        conn.execute(
            "INSERT OR REPLACE INTO franchise_tracking "
            "(collection_id, collection_name, total_parts, watched_parts, "
            " next_unreleased_tmdb_id, next_unreleased_title, next_unreleased_poster, "
            " next_release_date, last_checked, source_title_ids) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)",
            (coll_id, coll_name, total_parts, watched_count,
             next_unreleased["id"] if next_unreleased else None,
             next_unreleased.get("title") if next_unreleased else None,
             next_unreleased.get("poster_path") if next_unreleased else None,
             next_unreleased.get("release_date") if next_unreleased else None,
             source_ids_str)
        )

        if next_unreleased:
            alerts.append({
                "collection_name": coll_name,
                "collection_id": coll_id,
                "next_title": next_unreleased.get("title"),
                "next_release_date": next_unreleased.get("release_date"),
                "watched_parts": watched_count,
                "total_parts": total_parts,
            })

        checked += 1

    conn.commit()
    logger.info(f"Franchise check complete: {checked} collections checked, "
                f"{skipped} skipped, {len(alerts)} with unreleased parts")
    return alerts
