"""Tests for Netflix CSV parser — 6 test cases."""

import os
import tempfile

from ingestion.csv_parser import parse_netflix_csv


class TestParseSeriesWithSeason:
    def test_parse_series_with_season(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("Title,Date\nBreaking Bad: Season 1: Pilot,15/01/2023\n", encoding="utf-8")
        result = parse_netflix_csv(str(csv_file))
        assert len(result) == 1
        entry = result[0]
        assert entry["parsed_name"] == "Breaking Bad"
        assert entry["season_number"] == 1
        assert entry["episode_name"] == "Pilot"
        assert entry["media_type_hint"] == "tv"


class TestParseMovie:
    def test_parse_movie(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("Title,Date\nInception,05/03/2022\n", encoding="utf-8")
        result = parse_netflix_csv(str(csv_file))
        assert len(result) == 1
        entry = result[0]
        assert entry["parsed_name"] == "Inception"
        assert entry["season_number"] is None
        assert entry["episode_name"] is None
        assert entry["media_type_hint"] == "movie"


class TestParseHebrewTitle:
    def test_parse_hebrew_title(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "Title,Date\nהכלה מאיסטנבול: עונה 1: פרק 3,10/05/2024\n",
            encoding="utf-8",
        )
        result = parse_netflix_csv(str(csv_file))
        assert len(result) == 1
        entry = result[0]
        assert entry["season_number"] == 1
        assert entry["media_type_hint"] == "tv"


class TestParseDateDayfirst:
    def test_parse_date_dayfirst(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("Title,Date\nSomeMovie,15/01/2023\n", encoding="utf-8")
        result = parse_netflix_csv(str(csv_file))
        assert len(result) == 1
        assert result[0]["watch_date"] == "2023-01-15"


class TestSkipMalformedRow:
    def test_skip_malformed_row(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "Title,Date\n,\nInception,05/03/2022\n,15/01/2023\nGoodMovie,\n",
            encoding="utf-8",
        )
        result = parse_netflix_csv(str(csv_file))
        assert len(result) == 1
        assert result[0]["parsed_name"] == "Inception"


class TestFullCsvParse:
    def test_full_csv_parse(self, sample_csv_path):
        result = parse_netflix_csv(sample_csv_path)
        assert len(result) == 8
