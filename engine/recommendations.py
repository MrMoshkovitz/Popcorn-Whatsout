import json
import logging
from ingestion.tmdb_api import tmdb_get
from config import TMDB_LANGUAGE_PRIMARY
from engine.genre_map import get_genre_names

logger = logging.getLogger(__name__)

REC_CAP_MOVIE = 5
REC_CAP_TV = 3


def _is_already_watched(conn, tmdb_id: int, tmdb_type: str) -> bool:
    cursor = conn.execute(
        "SELECT 1 FROM titles WHERE tmdb_id = ? AND tmdb_type = ?",
        (tmdb_id, tmdb_type)
    )
    return cursor.fetchone() is not None


def purge_library_recommendations(conn) -> int:
    """Delete unseen recommendations for titles already in user's library."""
    cursor = conn.execute(
        "DELETE FROM recommendations WHERE recommended_tmdb_id IN "
        "(SELECT tmdb_id FROM titles) AND status = 'unseen'"
    )
    conn.commit()
    purged = cursor.rowcount
    logger.info(f"Purged {purged} recommendations for titles already in library")
    return purged


def _is_dismissed(conn, source_title_id: int, recommended_tmdb_id: int) -> bool:
    cursor = conn.execute(
        "SELECT 1 FROM recommendations "
        "WHERE source_title_id = ? AND recommended_tmdb_id = ? AND status = 'dismissed'",
        (source_title_id, recommended_tmdb_id)
    )
    return cursor.fetchone() is not None


def _upsert_recommendation(conn, source_title_id, rec_tmdb_id, rec_type, rec_title,
                           poster_path, vote_average, genres=None, collection_name=None,
                           overview=None, backdrop_path=None, release_year=None):
    conn.execute(
        "INSERT OR REPLACE INTO recommendations "
        "(source_title_id, recommended_tmdb_id, recommended_type, recommended_title, "
        " poster_path, tmdb_recommendation_score, collection_name, genres, "
        " overview, backdrop_path, release_year, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
        " COALESCE((SELECT status FROM recommendations "
        "   WHERE source_title_id = ? AND recommended_tmdb_id = ?), 'unseen'), "
        " CURRENT_TIMESTAMP)",
        (source_title_id, rec_tmdb_id, rec_type, rec_title,
         poster_path, vote_average, collection_name, genres,
         overview, backdrop_path, release_year,
         source_title_id, rec_tmdb_id)
    )


def _add_collection_recs(conn, tmdb_id: int, source_title_id: int):
    movie_data = tmdb_get(f"/movie/{tmdb_id}", {"language": TMDB_LANGUAGE_PRIMARY})
    if not movie_data:
        return 0
    collection = movie_data.get("belongs_to_collection")
    if not collection:
        return 0

    collection_id = collection["id"]
    coll_name = collection.get("name")
    collection_data = tmdb_get(f"/collection/{collection_id}", {"language": TMDB_LANGUAGE_PRIMARY})
    if not collection_data:
        return 0

    added = 0
    for part in collection_data.get("parts", []):
        if part["id"] == tmdb_id:
            continue
        if _is_already_watched(conn, part["id"], "movie"):
            continue
        if _is_dismissed(conn, source_title_id, part["id"]):
            continue
        if part.get("original_language") == "he":
            part_title = part.get("title", "")
        else:
            part_title = part.get("original_title") or part.get("title", "")
        genre_ids = part.get("genre_ids", [])
        genres_json = json.dumps(get_genre_names(genre_ids, "movie")) if genre_ids else None
        rel_date = part.get("release_date") or ""
        _upsert_recommendation(
            conn, source_title_id, part["id"], "movie",
            part_title, part.get("poster_path"),
            part.get("vote_average", 0),
            genres=genres_json, collection_name=coll_name,
            overview=part.get("overview"),
            backdrop_path=part.get("backdrop_path"),
            release_year=rel_date[:4] if rel_date else None,
        )
        added += 1
    return added


def generate_recommendations(conn, tmdb_id: int, tmdb_type: str, source_title_id: int) -> int:
    """Generate recommendations for one title. Returns count of new recs added."""
    cap = REC_CAP_MOVIE if tmdb_type == "movie" else REC_CAP_TV
    data = tmdb_get(f"/{tmdb_type}/{tmdb_id}/recommendations", {"language": TMDB_LANGUAGE_PRIMARY})
    if not data:
        return 0

    added = 0
    for result in data.get("results", []):
        if added >= cap:
            break
        rec_tmdb_id = result["id"]
        rec_type = result.get("media_type", tmdb_type)
        if _is_already_watched(conn, rec_tmdb_id, rec_type):
            continue
        if _is_dismissed(conn, source_title_id, rec_tmdb_id):
            continue

        if result.get("original_language") == "he":
            rec_title = result.get("title") or result.get("name", "")
        else:
            rec_title = result.get("original_title") or result.get("original_name") or result.get("title") or result.get("name", "")
        genre_ids = result.get("genre_ids", [])
        genres_json = json.dumps(get_genre_names(genre_ids, rec_type)) if genre_ids else None
        rel_date = result.get("release_date") or result.get("first_air_date") or ""
        _upsert_recommendation(
            conn, source_title_id, rec_tmdb_id, rec_type, rec_title,
            result.get("poster_path"), result.get("vote_average", 0),
            genres=genres_json,
            overview=result.get("overview"),
            backdrop_path=result.get("backdrop_path"),
            release_year=rel_date[:4] if rel_date else None,
        )
        added += 1

    # Collection detection for movies
    collection_added = 0
    if tmdb_type == "movie":
        collection_added = _add_collection_recs(conn, tmdb_id, source_title_id)

    conn.commit()
    total = added + collection_added
    logger.info(f"Generated {total} recommendations for title_id={source_title_id} "
                f"(tmdb_id={tmdb_id}, type={tmdb_type})")
    return total


def generate_all_recommendations(conn) -> dict:
    """Generate recommendations for all titles. Returns stats dict."""
    cursor = conn.execute("SELECT id, tmdb_id, tmdb_type FROM titles")
    titles = cursor.fetchall()

    stats = {"total_titles": len(titles), "total_recs": 0, "errors": 0}
    for title in titles:
        try:
            count = generate_recommendations(
                conn, title["tmdb_id"], title["tmdb_type"], title["id"]
            )
            stats["total_recs"] += count
        except Exception as e:
            logger.error(f"Error generating recs for title_id={title['id']}: {e}")
            stats["errors"] += 1

    # Score all recommendations after generation
    try:
        from engine.taste_scorer import score_all_recommendations
        score_all_recommendations(conn)
    except Exception as e:
        logger.error(f"Scoring failed: {e}")

    logger.info(f"Recommendation generation complete: {stats}")
    return stats
