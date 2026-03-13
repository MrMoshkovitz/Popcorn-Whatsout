"""Tests for new season checker — 4 test cases with mocked TMDB API."""

from unittest.mock import patch


def _seed_title(conn, tmdb_id, title_en="Test Show"):
    conn.execute(
        "INSERT INTO titles (tmdb_id, tmdb_type, title_en, match_status) VALUES (?, 'tv', ?, 'auto')",
        (tmdb_id, title_en),
    )
    conn.commit()
    cursor = conn.execute("SELECT id FROM titles WHERE tmdb_id = ? AND tmdb_type = 'tv'", (tmdb_id,))
    return cursor.fetchone()["id"]


def _seed_tracking(conn, title_id, tmdb_id, total_seasons=2, max_watched=2, status="watching"):
    conn.execute(
        "INSERT INTO series_tracking (title_id, tmdb_id, total_seasons_tmdb, max_watched_season, status) "
        "VALUES (?, ?, ?, ?, ?)",
        (title_id, tmdb_id, total_seasons, max_watched, status),
    )
    conn.commit()


class TestNewSeasonDetected:
    @patch("engine.new_season_checker.tmdb_get")
    def test_new_season_detected(self, mock_tmdb, db_conn):
        title_id = _seed_title(db_conn, 1396, "Breaking Bad")
        _seed_tracking(db_conn, title_id, 1396, total_seasons=4, max_watched=4)

        mock_tmdb.return_value = {
            "number_of_seasons": 5,
            "seasons": [
                {"season_number": 5, "air_date": "2013-08-11"},
            ],
        }

        from engine.new_season_checker import check_new_seasons
        alerts = check_new_seasons(db_conn)

        assert len(alerts) == 1
        assert alerts[0]["tmdb_id"] == 1396
        assert alerts[0]["new_season"] == 5
        assert alerts[0]["air_date"] == "2013-08-11"

        cursor = db_conn.execute(
            "SELECT total_seasons_tmdb FROM series_tracking WHERE title_id = ?", (title_id,)
        )
        assert cursor.fetchone()["total_seasons_tmdb"] == 5


class TestNoNewSeason:
    @patch("engine.new_season_checker.tmdb_get")
    def test_no_new_season(self, mock_tmdb, db_conn):
        title_id = _seed_title(db_conn, 1399, "Game of Thrones")
        _seed_tracking(db_conn, title_id, 1399, total_seasons=8, max_watched=8)

        mock_tmdb.return_value = {
            "number_of_seasons": 8,
            "seasons": [],
        }

        from engine.new_season_checker import check_new_seasons
        alerts = check_new_seasons(db_conn)

        assert len(alerts) == 0

        cursor = db_conn.execute(
            "SELECT last_checked FROM series_tracking WHERE title_id = ?", (title_id,)
        )
        assert cursor.fetchone()["last_checked"] is not None


class TestSkipCompletedSeries:
    @patch("engine.new_season_checker.tmdb_get")
    def test_skip_completed_series(self, mock_tmdb, db_conn):
        title_id = _seed_title(db_conn, 1399, "Game of Thrones")
        _seed_tracking(db_conn, title_id, 1399, total_seasons=8, max_watched=8, status="completed")

        from engine.new_season_checker import check_new_seasons
        alerts = check_new_seasons(db_conn)

        assert len(alerts) == 0
        mock_tmdb.assert_not_called()


class TestSkipDroppedSeries:
    @patch("engine.new_season_checker.tmdb_get")
    def test_skip_dropped_series(self, mock_tmdb, db_conn):
        title_id = _seed_title(db_conn, 66732, "Stranger Things")
        _seed_tracking(db_conn, title_id, 66732, total_seasons=4, max_watched=2, status="dropped")

        from engine.new_season_checker import check_new_seasons
        alerts = check_new_seasons(db_conn)

        assert len(alerts) == 0
        mock_tmdb.assert_not_called()
