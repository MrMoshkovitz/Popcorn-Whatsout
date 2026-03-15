"""Taste profile scoring for recommendation match percentages.

Computes a 0-100 match score based on genre overlap (70%) and rating similarity (30%).
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


def compute_match_score(user_profile, rec_genres, rec_vote_average):
    """Return 0-100 match percentage.

    70% genre overlap with user's top genres, 30% rating similarity.
    """
    genre_counts = user_profile.get('genre_counts', {})
    user_avg = user_profile.get('avg_rating', 7.0)

    if not genre_counts:
        return 50  # neutral if no data

    # Top genres by count
    total_genre_entries = sum(genre_counts.values())
    if total_genre_entries == 0:
        genre_score = 0.5
    else:
        # Calculate overlap score: how many of rec's genres appear in user's top genres
        overlap = 0
        for g in (rec_genres or []):
            if g in genre_counts:
                overlap += genre_counts[g] / total_genre_entries
        genre_score = min(overlap * 2, 1.0)  # normalize, cap at 1.0

    # Rating similarity: how close rec rating is to user average
    rec_rating = rec_vote_average or 5.0
    rating_diff = abs(rec_rating - user_avg)
    rating_score = max(0, 1.0 - rating_diff / 5.0)

    match = (genre_score * 0.7 + rating_score * 0.3) * 100
    return int(min(max(match, 0), 99))
