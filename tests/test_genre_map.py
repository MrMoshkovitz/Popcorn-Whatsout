"""Tests for genre ID to name mapping — 3 test cases."""

from unittest.mock import patch


class TestGenreIdToName:
    @patch("engine.genre_map.tmdb_get")
    def test_converts_ids_to_names(self, mock_tmdb):
        """Known genre IDs should return correct names."""
        import engine.genre_map as gm
        gm._loaded = False  # force reload

        def side_effect(endpoint, params=None):
            if "/genre/movie/list" in endpoint:
                return {"genres": [
                    {"id": 28, "name": "Action"},
                    {"id": 12, "name": "Adventure"},
                    {"id": 35, "name": "Comedy"},
                ]}
            if "/genre/tv/list" in endpoint:
                return {"genres": [
                    {"id": 18, "name": "Drama"},
                    {"id": 10759, "name": "Action & Adventure"},
                ]}
            return None

        mock_tmdb.side_effect = side_effect

        result = gm.get_genre_names([28, 12], "movie")
        assert result == ["Action", "Adventure"]

    @patch("engine.genre_map.tmdb_get")
    def test_unknown_ids_skipped(self, mock_tmdb):
        """Unknown genre IDs should be silently skipped."""
        import engine.genre_map as gm
        gm._loaded = False

        mock_tmdb.side_effect = lambda endpoint, params=None: {
            "genres": [{"id": 28, "name": "Action"}]
        }

        result = gm.get_genre_names([28, 9999], "movie")
        assert result == ["Action"]

    @patch("engine.genre_map.tmdb_get")
    def test_lazy_loading(self, mock_tmdb):
        """Genre lists should be fetched only once (cached after first call)."""
        import engine.genre_map as gm
        gm._loaded = False

        mock_tmdb.return_value = {"genres": [{"id": 28, "name": "Action"}]}

        gm.get_genre_names([28], "movie")
        gm.get_genre_names([28], "movie")

        # Should only call TMDB twice (movie list + tv list), not on second get_genre_names
        assert mock_tmdb.call_count == 2
