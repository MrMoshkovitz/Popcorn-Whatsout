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


if __name__ == '__main__':
    unittest.main()
