"""Tests for streaming availability checker — 4 test cases with mocked TMDB API."""

from unittest.mock import patch


def _seed_title(conn, tmdb_id, tmdb_type, title_en="Test Title"):
    conn.execute(
        "INSERT INTO titles (tmdb_id, tmdb_type, title_en, match_status) VALUES (?, ?, ?, 'auto')",
        (tmdb_id, tmdb_type, title_en),
    )
    conn.commit()


class TestFlatrateProviders:
    @patch("engine.availability.tmdb_get")
    def test_update_availability_flatrate(self, mock_tmdb, db_conn):
        _seed_title(db_conn, 550, "movie", "Fight Club")
        mock_tmdb.return_value = {
            "results": {
                "IL": {
                    "flatrate": [
                        {"provider_name": "Netflix", "logo_path": "/netflix.png"},
                        {"provider_name": "Disney Plus", "logo_path": "/disney.png"},
                    ]
                }
            }
        }

        from engine.availability import update_availability
        count = update_availability(db_conn, 550, "movie")

        assert count == 2
        cursor = db_conn.execute(
            "SELECT provider_name, monetization_type FROM streaming_availability "
            "WHERE tmdb_id = ? AND tmdb_type = ?",
            (550, "movie"),
        )
        rows = cursor.fetchall()
        providers = {row["provider_name"] for row in rows}
        assert providers == {"Netflix", "Disney Plus"}
        assert all(row["monetization_type"] == "flatrate" for row in rows)


class TestMultipleMonetizationTypes:
    @patch("engine.availability.tmdb_get")
    def test_update_availability_multiple_types(self, mock_tmdb, db_conn):
        _seed_title(db_conn, 550, "movie", "Fight Club")
        mock_tmdb.return_value = {
            "results": {
                "IL": {
                    "flatrate": [
                        {"provider_name": "Netflix", "logo_path": "/netflix.png"},
                    ],
                    "rent": [
                        {"provider_name": "Apple TV", "logo_path": "/apple.png"},
                    ],
                    "buy": [
                        {"provider_name": "Google Play", "logo_path": "/gplay.png"},
                        {"provider_name": "Apple TV", "logo_path": "/apple.png"},
                    ],
                }
            }
        }

        from engine.availability import update_availability
        count = update_availability(db_conn, 550, "movie")

        assert count == 4
        cursor = db_conn.execute(
            "SELECT provider_name, monetization_type FROM streaming_availability "
            "WHERE tmdb_id = ? AND tmdb_type = ?",
            (550, "movie"),
        )
        rows = cursor.fetchall()
        types = {row["monetization_type"] for row in rows}
        assert types == {"flatrate", "rent", "buy"}


class TestNoILProviders:
    @patch("engine.availability.tmdb_get")
    def test_no_il_providers(self, mock_tmdb, db_conn):
        _seed_title(db_conn, 550, "movie", "Fight Club")
        mock_tmdb.return_value = {
            "results": {
                "US": {
                    "flatrate": [
                        {"provider_name": "Hulu", "logo_path": "/hulu.png"},
                    ]
                }
            }
        }

        from engine.availability import update_availability
        count = update_availability(db_conn, 550, "movie")

        assert count == 0
        cursor = db_conn.execute(
            "SELECT COUNT(*) as cnt FROM streaming_availability "
            "WHERE tmdb_id = ? AND tmdb_type = ?",
            (550, "movie"),
        )
        assert cursor.fetchone()["cnt"] == 0


class TestFullReplace:
    @patch("engine.availability.tmdb_get")
    def test_full_replace(self, mock_tmdb, db_conn):
        _seed_title(db_conn, 550, "movie", "Fight Club")

        # Pre-existing provider data
        db_conn.execute(
            "INSERT INTO streaming_availability "
            "(tmdb_id, tmdb_type, provider_name, provider_logo_path, monetization_type) "
            "VALUES (?, ?, ?, ?, ?)",
            (550, "movie", "Old Provider", "/old.png", "flatrate"),
        )
        db_conn.commit()

        # New TMDB response with different providers
        mock_tmdb.return_value = {
            "results": {
                "IL": {
                    "flatrate": [
                        {"provider_name": "Netflix", "logo_path": "/netflix.png"},
                    ]
                }
            }
        }

        from engine.availability import update_availability
        count = update_availability(db_conn, 550, "movie")

        assert count == 1
        cursor = db_conn.execute(
            "SELECT provider_name FROM streaming_availability "
            "WHERE tmdb_id = ? AND tmdb_type = ?",
            (550, "movie"),
        )
        rows = cursor.fetchall()
        assert len(rows) == 1
        assert rows[0]["provider_name"] == "Netflix"
