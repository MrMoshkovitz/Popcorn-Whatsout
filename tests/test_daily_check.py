"""Tests for daily_check cron orchestrator — 4 test cases."""

from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock


def _seed_review_title(conn, tmdb_id, title_en, created_at):
    """Insert a title with match_status='review' and specific created_at."""
    conn.execute(
        "INSERT INTO titles (tmdb_id, tmdb_type, title_en, match_status, created_at) "
        "VALUES (?, 'movie', ?, 'review', ?)",
        (tmdb_id, title_en, created_at),
    )
    conn.commit()


class TestFullRunMonday:
    @patch("cron.daily_check.asyncio")
    @patch("cron.daily_check.sqlite3")
    @patch("cron.daily_check.datetime")
    def test_full_run_monday(self, mock_dt, mock_sqlite, mock_asyncio):
        """On Monday, all 5 phases run including recommendations."""
        mock_dt.today.return_value.weekday.return_value = 0
        mock_dt.now.return_value = datetime.now()
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        mock_conn = MagicMock()
        mock_sqlite.connect.return_value = mock_conn
        mock_conn.row_factory = None
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        with patch("engine.new_season_checker.check_new_seasons", return_value=[]) as mock_seasons, \
             patch("engine.availability.update_all_availability", return_value={"total_titles": 0, "total_providers": 0}) as mock_avail, \
             patch("engine.recommendations.generate_all_recommendations", return_value={"total_titles": 0, "total_recs": 0}) as mock_recs:

            from cron.daily_check import daily_check
            daily_check()

            mock_seasons.assert_called_once()
            mock_avail.assert_called_once()
            mock_recs.assert_called_once()


class TestFullRunNonMonday:
    @patch("cron.daily_check.asyncio")
    @patch("cron.daily_check.sqlite3")
    @patch("cron.daily_check.datetime")
    def test_full_run_non_monday(self, mock_dt, mock_sqlite, mock_asyncio):
        """On non-Monday, recommendations phase is skipped."""
        mock_dt.today.return_value.weekday.return_value = 1  # Tuesday
        mock_dt.now.return_value = datetime.now()
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        mock_conn = MagicMock()
        mock_sqlite.connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        with patch("engine.new_season_checker.check_new_seasons", return_value=[]) as mock_seasons, \
             patch("engine.availability.update_all_availability", return_value={"total_titles": 0, "total_providers": 0}) as mock_avail, \
             patch("engine.recommendations.generate_all_recommendations", return_value={"total_titles": 0, "total_recs": 0}) as mock_recs:

            from cron.daily_check import daily_check
            daily_check()

            mock_seasons.assert_called_once()
            mock_avail.assert_called_once()
            mock_recs.assert_not_called()


class TestPhaseErrorContinues:
    @patch("cron.daily_check.asyncio")
    @patch("cron.daily_check.sqlite3")
    @patch("cron.daily_check.datetime")
    def test_phase_error_continues(self, mock_dt, mock_sqlite, mock_asyncio):
        """If one phase raises an exception, remaining phases still run."""
        mock_dt.today.return_value.weekday.return_value = 0  # Monday
        mock_dt.now.return_value = datetime.now()
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        mock_conn = MagicMock()
        mock_sqlite.connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        with patch("engine.new_season_checker.check_new_seasons", side_effect=Exception("TMDB down")) as mock_seasons, \
             patch("engine.availability.update_all_availability", return_value={"total_titles": 0, "total_providers": 0}) as mock_avail, \
             patch("engine.recommendations.generate_all_recommendations", return_value={"total_titles": 0, "total_recs": 0}) as mock_recs:

            from cron.daily_check import daily_check
            daily_check()

            mock_seasons.assert_called_once()
            mock_avail.assert_called_once()
            mock_recs.assert_called_once()


class TestDisambiguationTimeout:
    def test_disambiguation_timeout(self, db_conn):
        """Stale review titles (>48h) are auto-resolved to 'auto'."""
        old_time = (datetime.now() - timedelta(hours=72)).strftime('%Y-%m-%d %H:%M:%S')
        recent_time = (datetime.now() - timedelta(hours=12)).strftime('%Y-%m-%d %H:%M:%S')

        _seed_review_title(db_conn, 100, "Old Movie", old_time)
        _seed_review_title(db_conn, 200, "Recent Movie", recent_time)

        # Create a proxy that delegates to db_conn but ignores close()
        proxy = MagicMock(wraps=db_conn)
        proxy.close = MagicMock()  # no-op close
        proxy.cursor.return_value = db_conn.cursor()
        proxy.commit = db_conn.commit
        proxy.execute = db_conn.execute

        with patch("cron.daily_check.sqlite3") as mock_sqlite, \
             patch("cron.daily_check.datetime") as mock_dt, \
             patch("cron.daily_check.asyncio"), \
             patch("engine.new_season_checker.check_new_seasons", return_value=[]), \
             patch("engine.availability.update_all_availability", return_value={"total_titles": 0, "total_providers": 0}):

            mock_dt.today.return_value.weekday.return_value = 2  # Not Monday
            mock_dt.now.return_value = datetime.now()
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            mock_sqlite.connect.return_value = proxy

            from cron.daily_check import daily_check
            daily_check()

        # Old title should be auto-resolved
        cursor = db_conn.execute(
            "SELECT match_status FROM titles WHERE tmdb_id = ?", (100,)
        )
        assert cursor.fetchone()["match_status"] == "auto"

        # Recent title should still be in review
        cursor = db_conn.execute(
            "SELECT match_status FROM titles WHERE tmdb_id = ?", (200,)
        )
        assert cursor.fetchone()["match_status"] == "review"
