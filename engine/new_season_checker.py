import logging
from datetime import datetime, timedelta

import dateutil.parser

from ingestion.tmdb_api import tmdb_get
from config import TMDB_LANGUAGE_PRIMARY

logger = logging.getLogger(__name__)

CHECK_INTERVAL_HOURS = 24


def _extract_season_air_date(tv_data: dict, season_number: int) -> str | None:
    for season in tv_data.get("seasons", []):
        if season.get("season_number") == season_number:
            return season.get("air_date")
    return None


def check_new_seasons(conn) -> list[dict]:
    """Check all watching series for new seasons. Returns list of alert dicts."""
    cursor = conn.execute(
        "SELECT st.id, st.title_id, st.max_watched_season, st.total_seasons_tmdb, "
        "       st.last_checked, t.tmdb_id, t.title_en, t.title_he, t.original_language "
        "FROM series_tracking st "
        "JOIN titles t ON st.title_id = t.id "
        "WHERE st.status = 'watching'"
    )
    tracked_series = cursor.fetchall()
    logger.info(f"Checking {len(tracked_series)} tracked series for new seasons")

    alerts = []
    checked = 0
    skipped = 0

    for row in tracked_series:
        last_checked = row["last_checked"]
        if last_checked:
            try:
                last_checked_dt = dateutil.parser.parse(last_checked)
                if datetime.utcnow() - last_checked_dt < timedelta(hours=CHECK_INTERVAL_HOURS):
                    logger.debug(f"Skipping {row['title_en']} — checked within {CHECK_INTERVAL_HOURS}h")
                    skipped += 1
                    continue
            except (ValueError, TypeError):
                pass

        tmdb_id = row["tmdb_id"]
        data = tmdb_get(f"/tv/{tmdb_id}", {"language": TMDB_LANGUAGE_PRIMARY})
        if not data:
            logger.warning(f"No TMDB data for tmdb_id={tmdb_id}")
            continue

        tmdb_total = data.get("number_of_seasons", 0)
        stored_total = row["total_seasons_tmdb"] or 0
        user_latest = row["max_watched_season"] or 0

        next_season = user_latest + 1
        next_air_date = _extract_season_air_date(data, next_season) if next_season <= tmdb_total else None
        total_episodes = data.get("number_of_episodes")

        if tmdb_total > stored_total and tmdb_total > user_latest:
            alerts.append({
                "title_id": row["title_id"],
                "tmdb_id": tmdb_id,
                "title_en": row["title_en"],
                "title_he": row["title_he"],
                "original_language": row["original_language"],
                "new_season": tmdb_total,
                "air_date": _extract_season_air_date(data, tmdb_total),
            })
            logger.info(f"New season detected: {row['title_en']} — season {tmdb_total}")

        conn.execute(
            "UPDATE series_tracking "
            "SET total_seasons_tmdb = ?, next_season_air_date = ?, "
            "    total_episodes_tmdb = ?, last_checked = CURRENT_TIMESTAMP "
            "WHERE id = ?",
            (tmdb_total, next_air_date, total_episodes, row["id"])
        )
        checked += 1

    conn.commit()
    logger.info(f"Season check complete: {checked} checked, {skipped} skipped, {len(alerts)} alerts")
    return alerts
