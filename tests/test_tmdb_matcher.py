"""Tests for TMDB matcher — 8 test cases with mocked TMDB API."""

from unittest.mock import patch

from ingestion.tmdb_matcher import (
    calculate_confidence,
    match_entries,
    _match_single,
)


def _make_entry(parsed_name, media_type_hint="movie", season_number=None,
                episode_name=None, watch_date="2023-01-15"):
    return {
        "title": parsed_name,
        "parsed_name": parsed_name,
        "season_number": season_number,
        "episode_name": episode_name,
        "watch_date": watch_date,
        "media_type_hint": media_type_hint,
    }


def _tmdb_result(title, tmdb_id=100, popularity=80.0, poster="/poster.jpg",
                 media_type="movie"):
    """Build a fake TMDB search result."""
    key = "title" if media_type == "movie" else "name"
    return {
        "id": tmdb_id,
        key: title,
        "popularity": popularity,
        "poster_path": poster,
    }


class TestHighConfidenceMatch:
    @patch("ingestion.tmdb_matcher.two_pass_search_with_type_fallback")
    def test_high_confidence_match(self, mock_search):
        mock_search.return_value = (
            _tmdb_result("Inception", tmdb_id=27205, popularity=90.0),
            "movie",
        )
        result = _match_single("Inception", "movie")
        assert result["tmdb_id"] == 27205
        assert result["confidence"] > 0.6
        assert result["match_status"] == "auto"


class TestLowConfidenceMatch:
    @patch("ingestion.tmdb_matcher.two_pass_search_with_type_fallback")
    def test_low_confidence_match(self, mock_search):
        mock_search.return_value = (
            _tmdb_result("Something Completely Different", tmdb_id=999, popularity=5.0),
            "movie",
        )
        result = _match_single("Inception", "movie")
        assert result["confidence"] < 0.6
        assert result["match_status"] == "review"


class TestNoResults:
    @patch("ingestion.tmdb_matcher.two_pass_search_with_type_fallback")
    def test_no_results(self, mock_search):
        mock_search.return_value = (None, "movie")
        result = _match_single("NonexistentTitle12345", "movie")
        assert result["tmdb_id"] is None
        assert result["confidence"] == 0.0
        assert result["match_status"] == "review"


class TestTypeFallbackTvToMovie:
    @patch("ingestion.tmdb_matcher.two_pass_search_with_type_fallback")
    def test_type_fallback_tv_to_movie(self, mock_search):
        mock_search.return_value = (
            _tmdb_result("Inception", tmdb_id=27205, popularity=90.0, media_type="movie"),
            "movie",
        )
        result = _match_single("Inception", "tv")
        assert result["tmdb_type"] == "movie"
        assert result["tmdb_id"] == 27205


class TestHebrewTitleMatch:
    @patch("ingestion.tmdb_matcher.two_pass_search_with_type_fallback")
    def test_hebrew_title_match(self, mock_search):
        mock_search.return_value = (
            {"id": 456, "name": "הכלה מאיסטנבול", "popularity": 50.0, "poster_path": "/he.jpg"},
            "tv",
        )
        result = _match_single("הכלה מאיסטנבול", "tv")
        assert result["tmdb_id"] == 456
        assert result["tmdb_type"] == "tv"
        assert result["confidence"] > 0.6


class TestEnglishFallback:
    @patch("ingestion.tmdb_api.search_tmdb")
    @patch("ingestion.tmdb_api.time.sleep")
    def test_english_fallback(self, mock_sleep, mock_search):
        """he-IL returns nothing, en-US succeeds."""
        mock_search.side_effect = [
            None,  # he-IL tv
            None,  # en-US tv (still nothing for tv)
            None,  # he-IL movie (fallback type)
            _tmdb_result("Rare Movie", tmdb_id=789, popularity=40.0),  # en-US movie
        ]
        result = _match_single("Rare Movie", "tv")
        assert result["tmdb_id"] == 789
        assert result["tmdb_type"] == "movie"


class TestDeduplication:
    @patch("ingestion.tmdb_matcher.two_pass_search_with_type_fallback")
    @patch("ingestion.tmdb_matcher.tmdb_get")
    def test_deduplication(self, mock_tmdb_get, mock_search, db_conn):
        """5 entries with same parsed_name → only 1 TMDB search call."""
        mock_search.return_value = (
            _tmdb_result("Breaking Bad", tmdb_id=1396, popularity=95.0, media_type="tv"),
            "tv",
        )
        mock_tmdb_get.return_value = {"number_of_seasons": 5}

        entries = [
            _make_entry("Breaking Bad", media_type_hint="tv", season_number=s,
                        episode_name=f"Episode {s}", watch_date=f"2023-01-{10+s:02d}")
            for s in range(1, 6)
        ]

        match_entries(entries, db_conn)

        assert mock_search.call_count == 1


class TestBatchDbInsert:
    @patch("ingestion.tmdb_matcher.two_pass_search_with_type_fallback")
    @patch("ingestion.tmdb_matcher.tmdb_get")
    def test_batch_db_insert(self, mock_tmdb_get, mock_search, db_conn):
        """After matching, titles and watch_history rows exist in DB."""
        mock_search.return_value = (
            _tmdb_result("Inception", tmdb_id=27205, popularity=90.0),
            "movie",
        )
        mock_tmdb_get.return_value = None

        entries = [
            _make_entry("Inception", watch_date="2023-01-15"),
            _make_entry("Inception", watch_date="2023-06-20"),
        ]

        stats = match_entries(entries, db_conn)

        # Title inserted
        cursor = db_conn.cursor()
        cursor.execute("SELECT * FROM titles WHERE tmdb_id = 27205")
        titles = cursor.fetchall()
        assert len(titles) == 1

        # Watch history rows inserted
        cursor.execute("SELECT * FROM watch_history")
        history = cursor.fetchall()
        assert len(history) == 2

        assert stats["matched"] == 1
