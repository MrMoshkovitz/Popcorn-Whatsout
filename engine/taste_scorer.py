"""Taste profile scoring for recommendation match percentages.

Computes a 0-99 match score based on 5 dimensions:
Genre overlap (0-40), Rating (0-20), Source affinity (0-20),
Recency (0-10), Streaming availability (0-10).
"""

import json
import logging

logger = logging.getLogger(__name__)


def compute_user_profile(conn):
    """Build user taste profile from library. Returns dict with genre_counts, avg_rating."""
    genre_counts = {}
    rows = conn.execute("SELECT genres, vote_average FROM titles WHERE genres IS NOT NULL").fetchall()

    total_rating = 0
    rating_count = 0

    for row in rows:
        try:
            genres = json.loads(row['genres'])
            for g in genres:
                genre_counts[g] = genre_counts.get(g, 0) + 1
        except (json.JSONDecodeError, TypeError):
            pass
        if row['vote_average']:
            total_rating += row['vote_average']
            rating_count += 1

    avg_rating = total_rating / rating_count if rating_count > 0 else 7.0
    return {'genre_counts': genre_counts, 'avg_rating': avg_rating}


def compute_match_score(user_profile, rec_genres, rec_vote_average,
                        source_watch_count=0, rec_release_year=None,
                        has_streaming=False):
    """Return 0-99 match score. 5 dimensions:
    Genre overlap (0-40), Rating (0-20), Source affinity (0-20),
    Recency (0-10), Streaming (0-10)."""
    genre_counts = user_profile.get('genre_counts', {})

    # Genre overlap (0-40)
    total_genre_entries = sum(genre_counts.values())
    if total_genre_entries == 0 or not rec_genres:
        genre_score = 20  # neutral
    else:
        overlap = 0
        for g in rec_genres:
            if g in genre_counts:
                overlap += genre_counts[g] / total_genre_entries
        genre_score = int(min(overlap * 2, 1.0) * 40)

    # Rating quality (0-20)
    rec_rating = rec_vote_average or 5.0
    rating_score = int((rec_rating / 10) * 20)

    # Source affinity (0-20): how many times user watched the source title
    affinity_score = min(source_watch_count * 2, 20)

    # Recency (0-10)
    if rec_release_year:
        try:
            year = int(rec_release_year)
            if year >= 2025:
                recency_score = 10
            elif year >= 2020:
                recency_score = 5
            else:
                recency_score = 2
        except (ValueError, TypeError):
            recency_score = 2
    else:
        recency_score = 2

    # Streaming availability (0-10)
    streaming_score = 10 if has_streaming else 0

    total = genre_score + rating_score + affinity_score + recency_score + streaming_score
    return int(min(max(total, 0), 99))


def score_all_recommendations(conn):
    """Score all unseen recommendations and update match_score column."""
    profile = compute_user_profile(conn)

    # Fetch all unseen recs with source watch count
    recs = conn.execute("""
        SELECT r.id, r.genres, r.tmdb_recommendation_score, r.release_year,
               r.recommended_tmdb_id, r.recommended_type,
               (SELECT COUNT(*) FROM watch_history wh
                WHERE wh.title_id = r.source_title_id) AS source_watch_count
        FROM recommendations r
        WHERE r.status = 'unseen'
    """).fetchall()

    # Batch: get all streaming availability tmdb_ids for quick lookup
    streaming_set = set()
    for row in conn.execute("SELECT DISTINCT tmdb_id FROM streaming_availability").fetchall():
        streaming_set.add(row['tmdb_id'])

    updated = 0
    for rec in recs:
        genres = []
        if rec['genres']:
            try:
                genres = json.loads(rec['genres'])
            except (json.JSONDecodeError, TypeError):
                pass

        has_streaming = rec['recommended_tmdb_id'] in streaming_set

        score = compute_match_score(
            profile, genres, rec['tmdb_recommendation_score'],
            source_watch_count=rec['source_watch_count'],
            rec_release_year=rec['release_year'],
            has_streaming=has_streaming,
        )

        conn.execute(
            "UPDATE recommendations SET match_score = ? WHERE id = ?",
            (score, rec['id'])
        )
        updated += 1

    conn.commit()
    logger.info(f"Scored {updated} recommendations")
    return updated
