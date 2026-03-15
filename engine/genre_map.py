"""Genre ID → name mapping via TMDB genre lists.

Fetches /genre/movie/list and /genre/tv/list once, caches in module-level dicts.
"""

import logging
from ingestion.tmdb_api import tmdb_get
from config import TMDB_LANGUAGE_PRIMARY

logger = logging.getLogger(__name__)

_movie_genres: dict[int, str] = {}
_tv_genres: dict[int, str] = {}
_loaded = False


def _load_genres():
    """Fetch genre lists from TMDB and cache them."""
    global _movie_genres, _tv_genres, _loaded
    if _loaded:
        return

    movie_data = tmdb_get("/genre/movie/list", {"language": TMDB_LANGUAGE_PRIMARY})
    if movie_data:
        _movie_genres = {g["id"]: g["name"] for g in movie_data.get("genres", [])}

    tv_data = tmdb_get("/genre/tv/list", {"language": TMDB_LANGUAGE_PRIMARY})
    if tv_data:
        _tv_genres = {g["id"]: g["name"] for g in tv_data.get("genres", [])}

    _loaded = True
    logger.info(f"Loaded {len(_movie_genres)} movie genres, {len(_tv_genres)} TV genres")


def get_genre_names(genre_ids: list[int], media_type: str = "movie") -> list[str]:
    """Convert genre IDs to names. Returns list of genre name strings."""
    _load_genres()
    genre_map = _movie_genres if media_type == "movie" else _tv_genres
    return [genre_map[gid] for gid in (genre_ids or []) if gid in genre_map]
