import os
import sys
import sqlite3
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestSendNewSeasonAlert(unittest.TestCase):
    """Test send_new_season_alert sends correct text and inline keyboard."""

    def test_send_new_season_alert(self):
        from bot.telegram_notifier import send_new_season_alert

        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock()

        asyncio.get_event_loop().run_until_complete(
            send_new_season_alert(
                bot=mock_bot,
                chat_id="12345",
                title_name="Breaking Bad",
                season_number=3,
                provider_name="Netflix",
                tmdb_id=1396
            )
        )

        mock_bot.send_message.assert_called_once()
        call_kwargs = mock_bot.send_message.call_args
        assert "Breaking Bad" in call_kwargs.kwargs["text"]
        assert "Season 3" in call_kwargs.kwargs["text"]
        assert "Netflix" in call_kwargs.kwargs["text"]
        assert call_kwargs.kwargs["parse_mode"] == "HTML"
        # Should have inline keyboard with watched/remind buttons
        keyboard = call_kwargs.kwargs["reply_markup"]
        buttons = keyboard.inline_keyboard
        assert len(buttons) == 1
        assert len(buttons[0]) == 2
        assert buttons[0][0].callback_data == "watched_1396"
        assert buttons[0][1].callback_data == "remind_1396"


class TestSendDisambiguation(unittest.TestCase):
    """Test send_disambiguation sends 3 candidates as inline buttons."""

    def test_send_disambiguation_three_candidates(self):
        from bot.telegram_notifier import send_disambiguation

        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock()

        candidates = [
            {"id": 100, "title": "The Matrix", "release_date": "1999-03-31"},
            {"id": 200, "name": "Matrix", "first_air_date": "1993-01-01"},
            {"id": 300, "title": "The Matrix Reloaded", "release_date": "2003-05-15"},
        ]

        asyncio.get_event_loop().run_until_complete(
            send_disambiguation(
                bot=mock_bot,
                chat_id="12345",
                raw_title="Matrix",
                candidates=candidates,
                title_id=42
            )
        )

        mock_bot.send_message.assert_called_once()
        call_kwargs = mock_bot.send_message.call_args
        assert "Matrix" in call_kwargs.kwargs["text"]
        assert call_kwargs.kwargs["parse_mode"] == "HTML"
        keyboard = call_kwargs.kwargs["reply_markup"]
        buttons = keyboard.inline_keyboard
        # 3 candidates = 3 rows, each with 1 button
        assert len(buttons) == 3
        assert buttons[0][0].callback_data == "disambig_42_100"
        assert buttons[1][0].callback_data == "disambig_42_200"
        assert buttons[2][0].callback_data == "disambig_42_300"
        # Check year is included in button text
        assert "(1999)" in buttons[0][0].text
        assert "(1993)" in buttons[1][0].text


class TestSendAdminAlert(unittest.TestCase):
    """Test send_admin_alert sends to admin chat with error details."""

    def test_send_admin_alert(self):
        from bot.telegram_notifier import send_admin_alert

        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock()

        asyncio.get_event_loop().run_until_complete(
            send_admin_alert(
                bot=mock_bot,
                chat_id="ADMIN_999",
                error_message="3 consecutive TMDB errors"
            )
        )

        mock_bot.send_message.assert_called_once()
        call_kwargs = mock_bot.send_message.call_args
        assert call_kwargs.kwargs["chat_id"] == "ADMIN_999"
        assert "3 consecutive TMDB errors" in call_kwargs.kwargs["text"]
        assert "Admin Alert" in call_kwargs.kwargs["text"]
        assert call_kwargs.kwargs["parse_mode"] == "HTML"


class TestCallbackHandlerDisambig(unittest.TestCase):
    """Test handle_callback with disambig data updates titles table."""

    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        with open(os.path.join(os.path.dirname(__file__), '..', 'db', 'schema.sql')) as f:
            self.conn.executescript(f.read())
        # Insert a title with review status
        self.conn.execute(
            "INSERT INTO titles (id, tmdb_id, tmdb_type, title_en, match_status) VALUES (?, ?, ?, ?, ?)",
            (10, 999, 'movie', 'Old Match', 'review')
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    @patch('bot.telegram_notifier.sqlite3')
    def test_callback_disambig_updates_title(self, mock_sqlite3):
        from bot.telegram_notifier import handle_callback

        # Use a mock connection to verify SQL calls without closing our real conn
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_sqlite3.connect.return_value = mock_conn
        mock_sqlite3.Row = sqlite3.Row

        # Build mock Update with callback data
        mock_query = AsyncMock()
        mock_query.data = "disambig_10_5555"
        mock_query.answer = AsyncMock()
        mock_query.edit_message_text = AsyncMock()

        mock_update = MagicMock()
        mock_update.callback_query = mock_query

        mock_context = MagicMock()

        asyncio.get_event_loop().run_until_complete(
            handle_callback(mock_update, mock_context)
        )

        mock_query.answer.assert_called_once()
        mock_query.edit_message_text.assert_called_once_with("Match confirmed!")

        # Verify the correct SQL was executed with parameterized query
        mock_cursor.execute.assert_called_once_with(
            "UPDATE titles SET tmdb_id = ?, match_status = 'auto' WHERE id = ?",
            (5555, 10)
        )
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
