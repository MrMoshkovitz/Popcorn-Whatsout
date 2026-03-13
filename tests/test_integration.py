"""End-to-end integration test: CSV → parse → match → DB."""

import os
from unittest.mock import patch, call

from ingestion.csv_parser import parse_netflix_csv
from ingestion.tmdb_matcher import match_entries


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')


def _tmdb_result(title, tmdb_id, popularity=80.0, poster="/poster.jpg", media_type="movie"):
    key = "title" if media_type == "movie" else "name"
    return {
        "id": tmdb_id,
        key: title,
        "popularity": popularity,
        "poster_path": poster,
    }


def _make_search_side_effect():
    """Map parsed_name → (result, type) for two_pass_search_with_type_fallback."""
    lookup = {
        "Breaking Bad": (_tmdb_result("Breaking Bad", 1396, 95.0, media_type="tv"), "tv"),
        "Inception": (_tmdb_result("Inception", 27205, 90.0), "movie"),
        "Mission": (_tmdb_result("Mission: Impossible - Fallout", 353081, 70.0), "movie"),
        "הכלה מאיסטנבול": (_tmdb_result("הכלה מאיסטנבול", 456, 50.0, media_type="tv"), "tv"),
        "Bandersnatch": (_tmdb_result("Bandersnatch", 9999, 60.0), "movie"),
        "Stranger Things": (_tmdb_result("Stranger Things", 66732, 99.0, media_type="tv"), "tv"),
    }

    def side_effect(query, media_type_hint):
        return lookup.get(query, (None, media_type_hint))

    return side_effect


class TestCsvToDbPipeline:
    """Full pipeline: parse sample CSV → mock TMDB match → verify DB state."""

    @patch("ingestion.tmdb_matcher.tmdb_get")
    @patch("ingestion.tmdb_matcher.two_pass_search_with_type_fallback")
    def test_csv_to_db_pipeline(self, mock_search, mock_tmdb_get, db_conn):
        mock_search.side_effect = _make_search_side_effect()
        # tmdb_get is called for TV series detail (number_of_seasons)
        mock_tmdb_get.return_value = {"number_of_seasons": 5}

        # Step 1: Parse CSV
        csv_path = os.path.join(FIXTURES_DIR, 'sample_netflix.csv')
        entries = parse_netflix_csv(csv_path)
        assert len(entries) == 8  # 8 rows in sample CSV

        # Step 2: Match and store
        stats = match_entries(entries, db_conn)

        cursor = db_conn.cursor()

        # Verify: correct number of unique titles
        cursor.execute("SELECT COUNT(*) FROM titles")
        title_count = cursor.fetchone()[0]
        assert title_count == 6  # 6 unique parsed_names

        # Verify: all watch_history entries present
        cursor.execute("SELECT COUNT(*) FROM watch_history")
        history_count = cursor.fetchone()[0]
        assert history_count == 8

        # Verify: series_tracking entries for TV shows
        cursor.execute("SELECT COUNT(*) FROM series_tracking")
        tracking_count = cursor.fetchone()[0]
        assert tracking_count == 3  # Breaking Bad, הכלה מאיסטנבול, Stranger Things

        # Verify: specific series_tracking data
        cursor.execute(
            "SELECT st.max_watched_season, st.status FROM series_tracking st "
            "JOIN titles t ON st.title_id = t.id WHERE t.tmdb_id = ?",
            (1396,)
        )
        bb = cursor.fetchone()
        assert bb["max_watched_season"] == 2  # Breaking Bad watched seasons 1 and 2
        assert bb["status"] == "watching"

        # Verify: confidence scores calculated
        cursor.execute("SELECT confidence, match_status FROM titles WHERE tmdb_id = ?", (27205,))
        inception = cursor.fetchone()
        assert inception["confidence"] > 0.6
        assert inception["match_status"] == "auto"

        # Verify: match stats
        assert stats["matched"] + stats["review"] + stats["errors"] == 6  # all unique names accounted for
        assert stats["matched"] > 0
        assert stats["errors"] == 0

        # Verify: deduplication — search called once per unique name
        assert mock_search.call_count == 6
