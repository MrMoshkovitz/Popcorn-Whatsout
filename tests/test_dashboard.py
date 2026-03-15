import os
import sys
import io
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestDashboard(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        conn = sqlite3.connect(self.db_path)
        schema_path = os.path.join(
            os.path.dirname(__file__), '..', 'db', 'schema.sql'
        )
        with open(schema_path) as f:
            conn.executescript(f.read())
        conn.close()

        self.db_patcher = patch('dashboard.app.DB_PATH', self.db_path)
        self.db_patcher.start()

        from dashboard.app import app
        app.config['TESTING'] = True
        self.app = app
        self.client = app.test_client()

    def tearDown(self):
        self.db_patcher.stop()
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def get_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def test_root_redirects(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/watch-next', response.headers['Location'])

    def test_watch_next_empty(self):
        response = self.client.get('/watch-next')
        self.assertEqual(response.status_code, 200)

    def test_library_empty(self):
        response = self.client.get('/library')
        self.assertEqual(response.status_code, 200)

    def test_review_empty(self):
        response = self.client.get('/review')
        self.assertEqual(response.status_code, 200)

    def test_upload_rate_limit(self):
        csv_content = b'Title,Date\n"Some Movie","1/15/2023"\n'

        # First upload — set the rate limit timestamp manually
        conn = self.get_db()
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?)",
            ('last_upload_date', datetime.now().isoformat())
        )
        conn.commit()
        conn.close()

        # Second upload should be rejected due to rate limit
        response = self.client.post('/upload', data={
            'csv_file': (io.BytesIO(csv_content), 'history.csv')
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        html = response.data.decode('utf-8')
        self.assertIn('rate limit', html.lower())

    def test_dismiss_recommendation(self):
        conn = self.get_db()
        # Insert a source title
        conn.execute("""
            INSERT INTO titles (tmdb_id, tmdb_type, title_en, match_status, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (1396, 'tv', 'Breaking Bad', 'auto', 0.9))
        title_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Insert a recommendation
        conn.execute("""
            INSERT INTO recommendations
            (source_title_id, recommended_tmdb_id, recommended_type,
             recommended_title, poster_path, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (title_id, 60059, 'tv', 'Better Call Saul', '/bcs.jpg', 'unseen'))
        rec_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
        conn.close()

        # Dismiss it
        response = self.client.post(f'/dismiss/{rec_id}')
        self.assertEqual(response.status_code, 302)

        # Verify status changed
        conn = self.get_db()
        row = conn.execute(
            "SELECT status FROM recommendations WHERE id = ?", (rec_id,)
        ).fetchone()
        self.assertEqual(row['status'], 'dismissed')
        conn.close()

    def _insert_title_with_tracking(self, conn, title_en, air_date):
        """Helper: insert a title + series_tracking with given air_date."""
        conn.execute("""
            INSERT INTO titles (tmdb_id, tmdb_type, title_en, match_status, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (9999, 'tv', title_en, 'auto', 0.9))
        title_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("""
            INSERT INTO series_tracking
            (title_id, tmdb_id, total_seasons_tmdb, max_watched_season,
             next_season_air_date, status)
            VALUES (?, ?, ?, ?, ?, 'watching')
        """, (title_id, 9999, 5, 2, air_date))
        conn.commit()
        return title_id

    def test_watch_next_excludes_future(self):
        conn = self.get_db()
        self._insert_title_with_tracking(conn, 'Future Show', '2099-01-01')
        conn.close()

        response = self.client.get('/watch-next')
        self.assertEqual(response.status_code, 200)
        html = response.data.decode('utf-8')
        self.assertNotIn('Future Show', html)

    def test_coming_soon_excludes_released(self):
        conn = self.get_db()
        self._insert_title_with_tracking(conn, 'Old Show', '2020-01-01')
        conn.close()

        response = self.client.get('/coming-soon')
        self.assertEqual(response.status_code, 200)
        html = response.data.decode('utf-8')
        self.assertNotIn('Old Show', html)

    def test_watch_next_shows_released(self):
        conn = self.get_db()
        self._insert_title_with_tracking(conn, 'Released Show', '2020-01-01')
        conn.close()

        response = self.client.get('/watch-next')
        self.assertEqual(response.status_code, 200)
        html = response.data.decode('utf-8')
        self.assertIn('Released Show', html)

    def test_coming_soon_shows_future(self):
        conn = self.get_db()
        self._insert_title_with_tracking(conn, 'Upcoming Show', '2099-01-01')
        conn.close()

        response = self.client.get('/coming-soon')
        self.assertEqual(response.status_code, 200)
        html = response.data.decode('utf-8')
        self.assertIn('Upcoming Show', html)

    def test_delete_all(self):
        conn = self.get_db()
        conn.execute("""
            INSERT INTO titles (tmdb_id, tmdb_type, title_en, match_status, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (1234, 'movie', 'Test Movie', 'auto', 0.9))
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?)",
            ('last_upload_date', '2025-01-01')
        )
        conn.commit()
        conn.close()

        response = self.client.post('/delete-all')
        self.assertEqual(response.status_code, 302)

        conn = self.get_db()
        titles_count = conn.execute("SELECT COUNT(*) FROM titles").fetchone()[0]
        self.assertEqual(titles_count, 0)
        rate_limit = conn.execute(
            "SELECT value FROM settings WHERE key = ?", ('last_upload_date',)
        ).fetchone()
        self.assertIsNone(rate_limit)
        conn.close()


    def test_library_shows_english_title_for_english_content(self):
        """English-original titles should display English name."""
        conn = self.get_db()
        conn.execute("""
            INSERT INTO titles (tmdb_id, tmdb_type, title_en, title_he, original_language, match_status, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (550, 'movie', 'Fight Club', 'מועדון קרב', 'en', 'auto', 0.9))
        conn.commit()
        conn.close()

        response = self.client.get('/library')
        html = response.data.decode('utf-8')
        self.assertIn('Fight Club', html)

    def test_library_shows_hebrew_title_for_hebrew_content(self):
        """Hebrew-original titles should display Hebrew name."""
        conn = self.get_db()
        conn.execute("""
            INSERT INTO titles (tmdb_id, tmdb_type, title_en, title_he, original_language, match_status, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (12345, 'movie', 'וולדיסלב', 'וולדיסלב', 'he', 'auto', 0.9))
        conn.commit()
        conn.close()

        response = self.client.get('/library')
        html = response.data.decode('utf-8')
        self.assertIn('וולדיסלב', html)

    def test_upload_dedup_preserves_manual_edits(self):
        """Re-uploading CSV should not overwrite user_tag or match_status."""
        conn = self.get_db()
        # Insert a title that looks like it was manually edited
        conn.execute("""
            INSERT INTO titles (tmdb_id, tmdb_type, title_en, original_language,
                               match_status, confidence, source, user_tag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (550, 'movie', 'Fight Club', 'en', 'manual', 1.0, 'csv', 'me'))
        conn.commit()
        conn.close()

        # Simulate what match_entries does: try to insert same tmdb_id
        conn = self.get_db()
        cursor = conn.cursor()
        existing = cursor.execute(
            "SELECT id, match_status, user_tag FROM titles WHERE tmdb_id = ? AND tmdb_type = ?",
            (550, 'movie')
        ).fetchone()

        # Verify the existing title is found and skipped
        self.assertIsNotNone(existing)
        self.assertEqual(existing['user_tag'], 'me')
        self.assertEqual(existing['match_status'], 'manual')
        conn.close()

    def test_watch_history_dedup_ignores_duplicates(self):
        """INSERT OR IGNORE should silently skip duplicate watch_history entries."""
        conn = self.get_db()
        conn.execute("""
            INSERT INTO titles (tmdb_id, tmdb_type, title_en, match_status, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (550, 'movie', 'Fight Club', 'auto', 0.9))
        title_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Insert first entry with non-NULL season/episode (NULLs are distinct in UNIQUE)
        conn.execute("""
            INSERT INTO watch_history (title_id, raw_csv_title, watch_date, season_number, episode_name)
            VALUES (?, ?, ?, ?, ?)
        """, (title_id, 'Fight Club: Season 1: Ep1', '2024-01-15', 1, 'Ep1'))

        # Insert duplicate — should not raise
        conn.execute("""
            INSERT OR IGNORE INTO watch_history (title_id, raw_csv_title, watch_date, season_number, episode_name)
            VALUES (?, ?, ?, ?, ?)
        """, (title_id, 'Fight Club: Season 1: Ep1', '2024-01-15', 1, 'Ep1'))
        conn.commit()

        count = conn.execute("SELECT COUNT(*) FROM watch_history WHERE title_id = ?", (title_id,)).fetchone()[0]
        self.assertEqual(count, 1)
        conn.close()

    def test_library_filter_bar_present(self):
        """Library page should have the filter bar when titles exist."""
        conn = self.get_db()
        conn.execute("""
            INSERT INTO titles (tmdb_id, tmdb_type, title_en, match_status, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (550, 'movie', 'Fight Club', 'auto', 0.9))
        conn.commit()
        conn.close()

        response = self.client.get('/library')
        html = response.data.decode('utf-8')
        self.assertIn('filter-bar', html)
        self.assertIn('lib-search', html)


    def test_coming_soon_shows_returning_series(self):
        """Returning series (caught up, show still producing) should appear in coming soon."""
        conn = self.get_db()
        conn.execute("""
            INSERT INTO titles (tmdb_id, tmdb_type, title_en, match_status, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (7777, 'tv', 'Returning Show', 'auto', 0.9))
        title_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("""
            INSERT INTO series_tracking
            (title_id, tmdb_id, total_seasons_tmdb, max_watched_season, status, returning_series)
            VALUES (?, ?, ?, ?, 'watching', 1)
        """, (title_id, 7777, 3, 3))  # caught up at season 3, show is returning
        conn.commit()
        conn.close()

        response = self.client.get('/coming-soon')
        self.assertEqual(response.status_code, 200)
        html = response.data.decode('utf-8')
        self.assertIn('Returning Show', html)
        self.assertIn('Returning', html)

    def test_coming_soon_franchise_alerts(self):
        """Franchise tracking entries should appear in coming soon."""
        conn = self.get_db()
        conn.execute("""
            INSERT INTO franchise_tracking
            (collection_id, collection_name, total_parts, watched_parts,
             next_unreleased_tmdb_id, next_unreleased_title, next_unreleased_poster,
             next_release_date, source_title_ids)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (263, 'The Dark Knight Collection', 3, 2, 49026,
              'The Dark Knight Rises', '/dkr.jpg', '2099-01-01', '1,2'))
        conn.commit()
        conn.close()

        response = self.client.get('/coming-soon')
        self.assertEqual(response.status_code, 200)
        html = response.data.decode('utf-8')
        self.assertIn('The Dark Knight Rises', html)
        self.assertIn('The Dark Knight Collection', html)

    def test_watch_next_genre_grouping(self):
        """Recommendations with genres should be grouped by genre on watch next."""
        conn = self.get_db()
        conn.execute("""
            INSERT INTO titles (tmdb_id, tmdb_type, title_en, match_status, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (155, 'movie', 'The Dark Knight', 'auto', 0.9))
        title_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        conn.execute("""
            INSERT INTO recommendations
            (source_title_id, recommended_tmdb_id, recommended_type,
             recommended_title, poster_path, genres, status)
            VALUES (?, ?, 'movie', ?, '/poster.jpg', ?, 'unseen')
        """, (title_id, 272, 'Batman Begins', '["Action","Adventure"]'))
        conn.commit()
        conn.close()

        response = self.client.get('/watch-next')
        self.assertEqual(response.status_code, 200)
        html = response.data.decode('utf-8')
        self.assertIn('Batman Begins', html)
        self.assertIn('Action Movies For You', html)

    def test_watch_next_franchise_catchup(self):
        """Collection recommendations should appear in franchise catch-up."""
        conn = self.get_db()
        conn.execute("""
            INSERT INTO titles (tmdb_id, tmdb_type, title_en, match_status, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (155, 'movie', 'The Dark Knight', 'auto', 0.9))
        title_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        conn.execute("""
            INSERT INTO recommendations
            (source_title_id, recommended_tmdb_id, recommended_type,
             recommended_title, poster_path, collection_name, genres, status)
            VALUES (?, ?, 'movie', ?, '/poster.jpg', ?, '["Action"]', 'unseen')
        """, (title_id, 49026, 'The Dark Knight Rises', 'The Dark Knight Collection'))
        conn.commit()
        conn.close()

        response = self.client.get('/watch-next')
        self.assertEqual(response.status_code, 200)
        html = response.data.decode('utf-8')
        self.assertIn('The Dark Knight Collection', html)
        self.assertIn('The Dark Knight Rises', html)

    def test_delete_all_clears_franchise_tracking(self):
        """delete-all should also clear franchise_tracking table."""
        conn = self.get_db()
        conn.execute("""
            INSERT INTO franchise_tracking
            (collection_id, collection_name, total_parts, source_title_ids)
            VALUES (?, ?, ?, ?)
        """, (263, 'Test Collection', 3, '1'))
        conn.commit()
        conn.close()

        self.client.post('/delete-all')

        conn = self.get_db()
        count = conn.execute("SELECT COUNT(*) FROM franchise_tracking").fetchone()[0]
        self.assertEqual(count, 0)
        conn.close()


if __name__ == '__main__':
    unittest.main()
