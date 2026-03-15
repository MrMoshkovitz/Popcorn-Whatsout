"""Tests for recommendation engine — 8 test cases with mocked TMDB API."""

import json
from unittest.mock import patch


def _seed_title(conn, tmdb_id, tmdb_type, title_en="Test Title"):
    conn.execute(
        "INSERT INTO titles (tmdb_id, tmdb_type, title_en, match_status) VALUES (?, ?, ?, 'auto')",
        (tmdb_id, tmdb_type, title_en),
    )
    conn.commit()
    cursor = conn.execute("SELECT id FROM titles WHERE tmdb_id = ? AND tmdb_type = ?",
                          (tmdb_id, tmdb_type))
    return cursor.fetchone()["id"]


def _seed_watch_history(conn, title_id, watch_date="2023-01-15"):
    conn.execute(
        "INSERT INTO watch_history (title_id, raw_csv_title, watch_date) VALUES (?, 'test', ?)",
        (title_id, watch_date),
    )
    conn.commit()


def _make_rec_result(title, tmdb_id, vote_average=7.5, media_type="movie", genre_ids=None):
    return {
        "id": tmdb_id,
        "title": title,
        "name": title,
        "media_type": media_type,
        "poster_path": "/poster.jpg",
        "vote_average": vote_average,
        "genre_ids": genre_ids or [],
    }


class TestMovieRecommendationsCap:
    @patch("engine.recommendations.tmdb_get")
    def test_movie_recs_capped_at_5(self, mock_tmdb, db_conn):
        title_id = _seed_title(db_conn, 155, "movie", "The Dark Knight")
        mock_tmdb.return_value = {
            "results": [_make_rec_result(f"Movie {i}", 1000 + i) for i in range(6)]
        }

        from engine.recommendations import generate_recommendations
        generate_recommendations(db_conn, 155, "movie", title_id)

        cursor = db_conn.execute(
            "SELECT COUNT(*) as cnt FROM recommendations WHERE source_title_id = ?",
            (title_id,),
        )
        assert cursor.fetchone()["cnt"] == 5


class TestTvRecommendationsCap:
    @patch("engine.recommendations.tmdb_get")
    def test_tv_recs_capped_at_3(self, mock_tmdb, db_conn):
        title_id = _seed_title(db_conn, 1396, "tv", "Breaking Bad")
        mock_tmdb.return_value = {
            "results": [_make_rec_result(f"Show {i}", 2000 + i, media_type="tv") for i in range(4)]
        }

        from engine.recommendations import generate_recommendations
        generate_recommendations(db_conn, 1396, "tv", title_id)

        cursor = db_conn.execute(
            "SELECT COUNT(*) as cnt FROM recommendations WHERE source_title_id = ?",
            (title_id,),
        )
        assert cursor.fetchone()["cnt"] == 3


class TestSkipAlreadyWatched:
    @patch("engine.recommendations.tmdb_get")
    def test_skip_watched_title(self, mock_tmdb, db_conn):
        source_id = _seed_title(db_conn, 155, "movie", "The Dark Knight")
        watched_id = _seed_title(db_conn, 157336, "movie", "Interstellar")
        _seed_watch_history(db_conn, watched_id)

        mock_tmdb.return_value = {
            "results": [
                _make_rec_result("Interstellar", 157336),
                _make_rec_result("Batman Begins", 272),
                _make_rec_result("The Prestige", 1124),
            ]
        }

        from engine.recommendations import generate_recommendations
        generate_recommendations(db_conn, 155, "movie", source_id)

        cursor = db_conn.execute(
            "SELECT recommended_tmdb_id FROM recommendations WHERE source_title_id = ?",
            (source_id,),
        )
        rec_ids = [row["recommended_tmdb_id"] for row in cursor.fetchall()]
        assert 157336 not in rec_ids
        assert 272 in rec_ids
        assert 1124 in rec_ids


class TestCollectionDetection:
    @patch("engine.recommendations.tmdb_get")
    def test_collection_parts_added(self, mock_tmdb, db_conn):
        source_id = _seed_title(db_conn, 155, "movie", "The Dark Knight")

        def side_effect(endpoint, params=None):
            if "/recommendations" in endpoint:
                return {"results": [_make_rec_result("Some Movie", 9999)]}
            if endpoint == "/movie/155":
                return {
                    "belongs_to_collection": {"id": 263, "name": "The Dark Knight Collection"}
                }
            if endpoint == "/collection/263":
                return {
                    "parts": [
                        {"id": 272, "title": "Batman Begins", "poster_path": "/bb.jpg", "vote_average": 7.7},
                        {"id": 155, "title": "The Dark Knight", "poster_path": "/dk.jpg", "vote_average": 9.0},
                        {"id": 49026, "title": "The Dark Knight Rises", "poster_path": "/dkr.jpg", "vote_average": 7.8},
                    ]
                }
            return None

        mock_tmdb.side_effect = side_effect

        from engine.recommendations import generate_recommendations
        generate_recommendations(db_conn, 155, "movie", source_id)

        cursor = db_conn.execute(
            "SELECT recommended_tmdb_id FROM recommendations WHERE source_title_id = ?",
            (source_id,),
        )
        rec_ids = [row["recommended_tmdb_id"] for row in cursor.fetchall()]
        assert 272 in rec_ids
        assert 49026 in rec_ids
        assert 155 not in rec_ids


class TestEmptyRecommendations:
    @patch("engine.recommendations.tmdb_get")
    def test_empty_results_no_crash(self, mock_tmdb, db_conn):
        title_id = _seed_title(db_conn, 999, "movie", "Obscure Film")
        mock_tmdb.return_value = {"results": []}

        from engine.recommendations import generate_recommendations
        count = generate_recommendations(db_conn, 999, "movie", title_id)

        assert count == 0
        cursor = db_conn.execute(
            "SELECT COUNT(*) as cnt FROM recommendations WHERE source_title_id = ?",
            (title_id,),
        )
        assert cursor.fetchone()["cnt"] == 0


class TestDismissedNotRegenerated:
    @patch("engine.recommendations.tmdb_get")
    def test_dismissed_rec_preserved(self, mock_tmdb, db_conn):
        source_id = _seed_title(db_conn, 155, "movie", "The Dark Knight")
        db_conn.execute(
            "INSERT INTO recommendations (source_title_id, recommended_tmdb_id, recommended_type, "
            "recommended_title, status) VALUES (?, ?, 'movie', 'The Dark Knight Rises', 'dismissed')",
            (source_id, 49026),
        )
        db_conn.commit()

        mock_tmdb.return_value = {
            "results": [
                _make_rec_result("The Dark Knight Rises", 49026),
                _make_rec_result("Batman Begins", 272),
            ]
        }

        from engine.recommendations import generate_recommendations
        generate_recommendations(db_conn, 155, "movie", source_id)

        cursor = db_conn.execute(
            "SELECT status FROM recommendations WHERE source_title_id = ? AND recommended_tmdb_id = ?",
            (source_id, 49026),
        )
        row = cursor.fetchone()
        assert row["status"] == "dismissed"

        cursor = db_conn.execute(
            "SELECT recommended_tmdb_id FROM recommendations WHERE source_title_id = ? AND status != 'dismissed'",
            (source_id,),
        )
        rec_ids = [r["recommended_tmdb_id"] for r in cursor.fetchall()]
        assert 272 in rec_ids
        assert 49026 not in rec_ids


class TestGenresStoredOnRecommendations:
    @patch("engine.recommendations.get_genre_names")
    @patch("engine.recommendations.tmdb_get")
    def test_genres_stored(self, mock_tmdb, mock_genres, db_conn):
        """Recommendations should store genres from TMDB genre_ids."""
        source_id = _seed_title(db_conn, 155, "movie", "The Dark Knight")
        mock_genres.return_value = ["Action", "Adventure"]
        mock_tmdb.return_value = {
            "results": [_make_rec_result("Batman Begins", 272, genre_ids=[28, 12])]
        }

        from engine.recommendations import generate_recommendations
        generate_recommendations(db_conn, 155, "movie", source_id)

        row = db_conn.execute(
            "SELECT genres FROM recommendations WHERE recommended_tmdb_id = ?",
            (272,),
        ).fetchone()
        assert row is not None
        genres = json.loads(row["genres"])
        assert "Action" in genres
        assert "Adventure" in genres


class TestCollectionNameStoredOnRecommendations:
    @patch("engine.recommendations.get_genre_names")
    @patch("engine.recommendations.tmdb_get")
    def test_collection_name_stored(self, mock_tmdb, mock_genres, db_conn):
        """Collection recs should store collection_name."""
        source_id = _seed_title(db_conn, 155, "movie", "The Dark Knight")
        mock_genres.return_value = ["Action"]

        def side_effect(endpoint, params=None):
            if "/recommendations" in endpoint:
                return {"results": []}
            if endpoint == "/movie/155":
                return {"belongs_to_collection": {"id": 263, "name": "The Dark Knight Collection"}}
            if endpoint == "/collection/263":
                return {
                    "name": "The Dark Knight Collection",
                    "parts": [
                        {"id": 272, "title": "Batman Begins", "poster_path": "/bb.jpg",
                         "vote_average": 7.7, "genre_ids": [28]},
                        {"id": 155, "title": "The Dark Knight", "poster_path": "/dk.jpg",
                         "vote_average": 9.0, "genre_ids": [28]},
                    ],
                }
            return None

        mock_tmdb.side_effect = side_effect

        from engine.recommendations import generate_recommendations
        generate_recommendations(db_conn, 155, "movie", source_id)

        row = db_conn.execute(
            "SELECT collection_name FROM recommendations WHERE recommended_tmdb_id = ?",
            (272,),
        ).fetchone()
        assert row is not None
        assert row["collection_name"] == "The Dark Knight Collection"
