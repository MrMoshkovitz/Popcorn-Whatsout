"""Tests for franchise/collection tracking — 6 test cases with mocked TMDB API."""

from unittest.mock import patch


def _seed_movie(conn, tmdb_id, title_en="Test Movie"):
    conn.execute(
        "INSERT INTO titles (tmdb_id, tmdb_type, title_en, match_status) VALUES (?, 'movie', ?, 'auto')",
        (tmdb_id, title_en),
    )
    conn.commit()
    row = conn.execute("SELECT id FROM titles WHERE tmdb_id = ? AND tmdb_type = 'movie'",
                       (tmdb_id,)).fetchone()
    return row["id"]


def _seed_watch_history(conn, title_id, watch_date="2023-01-15"):
    conn.execute(
        "INSERT INTO watch_history (title_id, raw_csv_title, watch_date) VALUES (?, 'test', ?)",
        (title_id, watch_date),
    )
    conn.commit()


class TestCollectionDetection:
    @patch("engine.franchise_checker.tmdb_get")
    def test_movie_with_collection(self, mock_tmdb, db_conn):
        """Movie in a collection should create a franchise_tracking row."""
        title_id = _seed_movie(db_conn, 155, "The Dark Knight")
        _seed_watch_history(db_conn, title_id)

        def side_effect(endpoint, params=None):
            if endpoint == "/movie/155":
                return {"belongs_to_collection": {"id": 263, "name": "The Dark Knight Collection"}}
            if endpoint == "/collection/263":
                return {
                    "name": "The Dark Knight Collection",
                    "parts": [
                        {"id": 272, "title": "Batman Begins", "poster_path": "/bb.jpg", "release_date": "2005-06-15"},
                        {"id": 155, "title": "The Dark Knight", "poster_path": "/dk.jpg", "release_date": "2008-07-18"},
                        {"id": 49026, "title": "The Dark Knight Rises", "poster_path": "/dkr.jpg", "release_date": "2012-07-20"},
                    ],
                }
            return None

        mock_tmdb.side_effect = side_effect

        from engine.franchise_checker import check_franchises
        alerts = check_franchises(db_conn)

        row = db_conn.execute("SELECT * FROM franchise_tracking WHERE collection_id = 263").fetchone()
        assert row is not None
        assert row["collection_name"] == "The Dark Knight Collection"
        assert row["total_parts"] == 3
        assert row["watched_parts"] == 1  # only Dark Knight has watch_history

    @patch("engine.franchise_checker.tmdb_get")
    def test_movie_without_collection(self, mock_tmdb, db_conn):
        """Movie not in a collection should not create franchise_tracking."""
        _seed_movie(db_conn, 550, "Fight Club")

        mock_tmdb.return_value = {"belongs_to_collection": None}

        from engine.franchise_checker import check_franchises
        check_franchises(db_conn)

        count = db_conn.execute("SELECT COUNT(*) as cnt FROM franchise_tracking").fetchone()["cnt"]
        assert count == 0


class TestUnreleasedPartDetection:
    @patch("engine.franchise_checker.tmdb_get")
    def test_unreleased_future_date(self, mock_tmdb, db_conn):
        """Part with future release_date should be flagged as next unreleased."""
        title_id = _seed_movie(db_conn, 100, "Movie 1")
        _seed_watch_history(db_conn, title_id)

        def side_effect(endpoint, params=None):
            if endpoint == "/movie/100":
                return {"belongs_to_collection": {"id": 50, "name": "Test Collection"}}
            if endpoint == "/collection/50":
                return {
                    "name": "Test Collection",
                    "parts": [
                        {"id": 100, "title": "Movie 1", "release_date": "2020-01-01"},
                        {"id": 101, "title": "Movie 2", "release_date": "2099-12-31", "poster_path": "/m2.jpg"},
                    ],
                }
            return None

        mock_tmdb.side_effect = side_effect

        from engine.franchise_checker import check_franchises
        alerts = check_franchises(db_conn)

        row = db_conn.execute("SELECT * FROM franchise_tracking WHERE collection_id = 50").fetchone()
        assert row["next_unreleased_tmdb_id"] == 101
        assert row["next_unreleased_title"] == "Movie 2"
        assert len(alerts) == 1

    @patch("engine.franchise_checker.tmdb_get")
    def test_unreleased_null_date(self, mock_tmdb, db_conn):
        """Part with NULL release_date should be considered unreleased."""
        title_id = _seed_movie(db_conn, 200, "Movie A")
        _seed_watch_history(db_conn, title_id)

        def side_effect(endpoint, params=None):
            if endpoint == "/movie/200":
                return {"belongs_to_collection": {"id": 60, "name": "Another Collection"}}
            if endpoint == "/collection/60":
                return {
                    "name": "Another Collection",
                    "parts": [
                        {"id": 200, "title": "Movie A", "release_date": "2020-01-01"},
                        {"id": 201, "title": "Movie B", "release_date": None},
                    ],
                }
            return None

        mock_tmdb.side_effect = side_effect

        from engine.franchise_checker import check_franchises
        check_franchises(db_conn)

        row = db_conn.execute("SELECT * FROM franchise_tracking WHERE collection_id = 60").fetchone()
        assert row["next_unreleased_tmdb_id"] == 201


class TestWatchedPartsCount:
    @patch("engine.franchise_checker.tmdb_get")
    def test_multiple_watched_parts(self, mock_tmdb, db_conn):
        """watched_parts should count movies with watch_history entries."""
        id1 = _seed_movie(db_conn, 300, "Part 1")
        _seed_watch_history(db_conn, id1)
        id2 = _seed_movie(db_conn, 301, "Part 2")
        _seed_watch_history(db_conn, id2)
        _seed_movie(db_conn, 302, "Part 3")  # not watched

        def side_effect(endpoint, params=None):
            if endpoint in ("/movie/300", "/movie/301", "/movie/302"):
                return {"belongs_to_collection": {"id": 70, "name": "Trilogy"}}
            if endpoint == "/collection/70":
                return {
                    "name": "Trilogy",
                    "parts": [
                        {"id": 300, "title": "Part 1", "release_date": "2020-01-01"},
                        {"id": 301, "title": "Part 2", "release_date": "2021-01-01"},
                        {"id": 302, "title": "Part 3", "release_date": "2022-01-01"},
                    ],
                }
            return None

        mock_tmdb.side_effect = side_effect

        from engine.franchise_checker import check_franchises
        check_franchises(db_conn)

        row = db_conn.execute("SELECT * FROM franchise_tracking WHERE collection_id = 70").fetchone()
        assert row["watched_parts"] == 2
        assert row["total_parts"] == 3


class TestCollectionDedup:
    @patch("engine.franchise_checker.tmdb_get")
    def test_two_movies_same_collection_one_row(self, mock_tmdb, db_conn):
        """Two watched movies from same collection should produce one franchise_tracking row."""
        id1 = _seed_movie(db_conn, 400, "HP 1")
        _seed_watch_history(db_conn, id1)
        id2 = _seed_movie(db_conn, 401, "HP 3")
        _seed_watch_history(db_conn, id2)

        call_count = {"collection": 0}

        def side_effect(endpoint, params=None):
            if endpoint in ("/movie/400", "/movie/401"):
                return {"belongs_to_collection": {"id": 80, "name": "Harry Potter"}}
            if endpoint == "/collection/80":
                call_count["collection"] += 1
                return {
                    "name": "Harry Potter",
                    "parts": [
                        {"id": 400, "title": "HP 1", "release_date": "2001-01-01"},
                        {"id": 401, "title": "HP 3", "release_date": "2004-01-01"},
                        {"id": 402, "title": "HP 5", "release_date": "2099-01-01", "poster_path": "/hp5.jpg"},
                    ],
                }
            return None

        mock_tmdb.side_effect = side_effect

        from engine.franchise_checker import check_franchises
        check_franchises(db_conn)

        count = db_conn.execute("SELECT COUNT(*) as cnt FROM franchise_tracking").fetchone()["cnt"]
        assert count == 1
        # Collection endpoint should only be called once (deduped by collection_id)
        assert call_count["collection"] == 1

        row = db_conn.execute("SELECT * FROM franchise_tracking WHERE collection_id = 80").fetchone()
        assert row["watched_parts"] == 2
        assert str(id1) in row["source_title_ids"]
        assert str(id2) in row["source_title_ids"]
