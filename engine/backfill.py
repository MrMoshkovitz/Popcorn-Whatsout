"""Backfill genres for existing titles/recommendations and populate franchise_tracking.

Run manually: python engine/backfill.py
Also callable from cron when NULL genres exist.
"""

import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ingestion.tmdb_api import tmdb_get
from config import DB_PATH, TMDB_LANGUAGE_PRIMARY
from engine.genre_map import get_genre_names

logger = logging.getLogger(__name__)


def backfill_genres(conn):
    """Fetch genres from TMDB for titles + recommendations with NULL genres."""
    # Backfill titles
    rows = conn.execute(
        "SELECT id, tmdb_id, tmdb_type FROM titles WHERE genres IS NULL"
    ).fetchall()
    logger.info(f"Backfilling genres for {len(rows)} titles")

    updated = 0
    for row in rows:
        data = tmdb_get(f"/{row['tmdb_type']}/{row['tmdb_id']}",
                        {"language": TMDB_LANGUAGE_PRIMARY})
        if not data:
            continue
        genre_names = [g["name"] for g in data.get("genres", [])]
        if genre_names:
            conn.execute(
                "UPDATE titles SET genres = ? WHERE id = ?",
                (json.dumps(genre_names), row["id"])
            )
            updated += 1

    # Backfill recommendations
    rec_rows = conn.execute(
        "SELECT id, recommended_tmdb_id, recommended_type FROM recommendations WHERE genres IS NULL"
    ).fetchall()
    logger.info(f"Backfilling genres for {len(rec_rows)} recommendations")

    rec_updated = 0
    for row in rec_rows:
        data = tmdb_get(f"/{row['recommended_type']}/{row['recommended_tmdb_id']}",
                        {"language": TMDB_LANGUAGE_PRIMARY})
        if not data:
            continue
        genre_names = [g["name"] for g in data.get("genres", [])]
        if genre_names:
            conn.execute(
                "UPDATE recommendations SET genres = ? WHERE id = ?",
                (json.dumps(genre_names), row["id"])
            )
            rec_updated += 1

    conn.commit()
    logger.info(f"Genre backfill complete: {updated} titles, {rec_updated} recommendations")
    return {"titles": updated, "recommendations": rec_updated}


def backfill_enrichment(conn):
    """Fetch overview/backdrop/vote_average/release_year for titles + recs with NULL values."""
    # Backfill titles
    rows = conn.execute(
        "SELECT id, tmdb_id, tmdb_type FROM titles WHERE overview IS NULL OR backdrop_path IS NULL"
    ).fetchall()
    logger.info(f"Backfilling enrichment for {len(rows)} titles")

    updated = 0
    for row in rows:
        data = tmdb_get(f"/{row['tmdb_type']}/{row['tmdb_id']}",
                        {"language": TMDB_LANGUAGE_PRIMARY})
        if not data:
            continue
        rel_date = data.get("release_date") or data.get("first_air_date") or ""
        conn.execute(
            "UPDATE titles SET overview = ?, backdrop_path = ?, vote_average = ?, release_year = ? WHERE id = ?",
            (data.get("overview"), data.get("backdrop_path"),
             data.get("vote_average"), rel_date[:4] if rel_date else None, row["id"])
        )
        updated += 1

    # Backfill recommendations
    rec_rows = conn.execute(
        "SELECT id, recommended_tmdb_id, recommended_type FROM recommendations "
        "WHERE overview IS NULL OR backdrop_path IS NULL"
    ).fetchall()
    logger.info(f"Backfilling enrichment for {len(rec_rows)} recommendations")

    rec_updated = 0
    for row in rec_rows:
        data = tmdb_get(f"/{row['recommended_type']}/{row['recommended_tmdb_id']}",
                        {"language": TMDB_LANGUAGE_PRIMARY})
        if not data:
            continue
        rel_date = data.get("release_date") or data.get("first_air_date") or ""
        conn.execute(
            "UPDATE recommendations SET overview = ?, backdrop_path = ?, release_year = ? WHERE id = ?",
            (data.get("overview"), data.get("backdrop_path"),
             rel_date[:4] if rel_date else None, row["id"])
        )
        rec_updated += 1

    conn.commit()
    logger.info(f"Enrichment backfill complete: {updated} titles, {rec_updated} recommendations")
    return {"titles": updated, "recommendations": rec_updated}


def backfill_franchises(conn):
    """Initial franchise_tracking population for all existing movies."""
    from engine.franchise_checker import check_franchises
    alerts = check_franchises(conn)
    logger.info(f"Franchise backfill complete: {len(alerts)} collections with unreleased parts")
    return alerts


if __name__ == "__main__":
    import sqlite3
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        backfill_genres(conn)
        backfill_enrichment(conn)
        backfill_franchises(conn)
    finally:
        conn.close()
