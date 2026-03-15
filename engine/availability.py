import logging
from ingestion.tmdb_api import tmdb_get
from config import WATCH_REGION

logger = logging.getLogger(__name__)


def update_availability(conn, tmdb_id: int, tmdb_type: str) -> int:
    """Update streaming availability for one title. Returns provider count."""
    data = tmdb_get(f"/{tmdb_type}/{tmdb_id}/watch/providers", {"watch_region": WATCH_REGION})
    if data is None:
        return 0

    # Delete old data
    conn.execute(
        "DELETE FROM streaming_availability WHERE tmdb_id = ? AND tmdb_type = ?",
        (tmdb_id, tmdb_type)
    )

    # Extract IL region
    il_data = data.get("results", {}).get("IL")
    if il_data is None:
        return 0

    # Insert fresh data for each monetization type
    count = 0
    for monetization_type in ["flatrate", "rent", "buy"]:
        for provider in il_data.get(monetization_type, []):
            conn.execute(
                "INSERT INTO streaming_availability "
                "(tmdb_id, tmdb_type, provider_name, provider_logo_path, "
                " monetization_type, last_updated) "
                "VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                (tmdb_id, tmdb_type,
                 provider["provider_name"], provider["logo_path"],
                 monetization_type)
            )
            count += 1

    logger.info(f"Updated availability for tmdb_id={tmdb_id} ({tmdb_type}): {count} providers")
    return count


def update_all_availability(conn) -> dict:
    """Update availability for all titles. Returns stats dict."""
    cursor = conn.execute("SELECT tmdb_id, tmdb_type FROM titles")
    titles = cursor.fetchall()

    stats = {"total_titles": len(titles), "total_providers": 0, "errors": 0}
    for title in titles:
        try:
            count = update_availability(conn, title["tmdb_id"], title["tmdb_type"])
            stats["total_providers"] += count
        except Exception as e:
            logger.error(f"Error updating availability for tmdb_id={title['tmdb_id']}: {e}")
            stats["errors"] += 1

    conn.commit()
    logger.info(f"Availability update complete: {stats}")
    return stats
