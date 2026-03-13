import time
import logging
import requests
from config import TMDB_API_KEY, TMDB_BASE_URL, TMDB_LANGUAGE_PRIMARY, TMDB_LANGUAGE_FALLBACK, API_DELAY_SECONDS

logger = logging.getLogger(__name__)


def tmdb_get(endpoint: str, params: dict = None) -> dict | None:
    time.sleep(API_DELAY_SECONDS)
    url = f"{TMDB_BASE_URL}{endpoint}"
    params = params or {}
    params["api_key"] = TMDB_API_KEY
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"TMDB API error: {endpoint} - {e}")
        return None


def search_tmdb(media_type: str, query: str, language: str) -> dict | None:
    data = tmdb_get(f"/search/{media_type}", {"query": query, "language": language})
    if data and data.get("results"):
        return data["results"][0]
    return None


def two_pass_search(media_type: str, query: str) -> dict | None:
    result = search_tmdb(media_type, query, TMDB_LANGUAGE_PRIMARY)
    if not result:
        result = search_tmdb(media_type, query, TMDB_LANGUAGE_FALLBACK)
    return result


def two_pass_search_with_type_fallback(query: str, preferred_type: str) -> tuple[dict | None, str]:
    fallback_type = "movie" if preferred_type == "tv" else "tv"
    result = two_pass_search(preferred_type, query)
    if result:
        return result, preferred_type
    result = two_pass_search(fallback_type, query)
    if result:
        return result, fallback_type
    return None, preferred_type
