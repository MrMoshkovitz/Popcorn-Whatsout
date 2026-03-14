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


class TestHelpCommand(unittest.TestCase):
    """Test /help command returns command list."""

    def test_help_command(self):
        from bot.telegram_notifier import help_command

        mock_update = MagicMock()
        mock_update.message = AsyncMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()

        asyncio.get_event_loop().run_until_complete(
            help_command(mock_update, mock_context)
        )

        mock_update.message.reply_text.assert_called_once()
        text = mock_update.message.reply_text.call_args[0][0]
        assert "/start" in text
        assert "/recommendations" in text
        assert "/help" in text


class TestRecommendationsWithPoster(unittest.TestCase):
    """Test /recommendations sends poster photos and streaming info."""

    @patch('bot.telegram_notifier.sqlite3')
    def test_recommendations_with_poster_and_providers(self, mock_sqlite3):
        from bot.telegram_notifier import recommendations_command

        mock_conn = MagicMock()
        mock_sqlite3.connect.return_value = mock_conn
        mock_sqlite3.Row = sqlite3.Row
        mock_conn.row_factory = None

        # Simulate a recommendation row with poster and providers
        mock_row = {
            'recommended_title': 'Inception',
            'poster_path': '/abc123.jpg',
            'recommended_tmdb_id': 27205,
            'recommended_type': 'movie',
            'providers': 'Netflix, Apple TV'
        }
        mock_conn.execute.return_value.fetchall.return_value = [mock_row]

        mock_update = MagicMock()
        mock_update.message = AsyncMock()
        mock_update.message.reply_photo = AsyncMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()

        asyncio.get_event_loop().run_until_complete(
            recommendations_command(mock_update, mock_context)
        )

        mock_update.message.reply_photo.assert_called_once()
        call_kwargs = mock_update.message.reply_photo.call_args
        assert 'abc123.jpg' in call_kwargs.kwargs['photo']
        assert 'Inception' in call_kwargs.kwargs['caption']
        assert 'Netflix' in call_kwargs.kwargs['caption']

    @patch('bot.telegram_notifier.sqlite3')
    def test_recommendations_no_poster_falls_back_to_text(self, mock_sqlite3):
        from bot.telegram_notifier import recommendations_command

        mock_conn = MagicMock()
        mock_sqlite3.connect.return_value = mock_conn
        mock_sqlite3.Row = sqlite3.Row
        mock_conn.row_factory = None

        mock_row = {
            'recommended_title': 'Obscure Film',
            'poster_path': None,
            'recommended_tmdb_id': 99999,
            'recommended_type': 'movie',
            'providers': None
        }
        mock_conn.execute.return_value.fetchall.return_value = [mock_row]

        mock_update = MagicMock()
        mock_update.message = AsyncMock()
        mock_update.message.reply_photo = AsyncMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()

        asyncio.get_event_loop().run_until_complete(
            recommendations_command(mock_update, mock_context)
        )

        mock_update.message.reply_photo.assert_not_called()
        mock_update.message.reply_text.assert_called_once()
        text = mock_update.message.reply_text.call_args[0][0]
        assert 'Obscure Film' in text


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


class TestAddCommand(unittest.TestCase):
    """Test /add command sends search results as inline keyboard."""

    @patch('bot.telegram_notifier.tmdb_get')
    def test_add_command_sends_keyboard(self, mock_tmdb):
        from bot.telegram_notifier import add_command

        mock_tmdb.return_value = {
            'results': [
                {'id': 550, 'media_type': 'movie', 'title': 'Fight Club', 'release_date': '1999-10-15'},
                {'id': 1396, 'media_type': 'tv', 'name': 'Breaking Bad', 'first_air_date': '2008-01-20'},
            ]
        }

        mock_update = MagicMock()
        mock_update.message = AsyncMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()
        mock_context.args = ['fight', 'club']

        asyncio.get_event_loop().run_until_complete(
            add_command(mock_update, mock_context)
        )

        mock_update.message.reply_text.assert_called_once()
        call_kwargs = mock_update.message.reply_text.call_args
        keyboard = call_kwargs.kwargs.get('reply_markup')
        assert keyboard is not None
        buttons = keyboard.inline_keyboard
        assert len(buttons) == 2
        assert 'add_550_movie' in buttons[0][0].callback_data
        assert 'add_1396_tv' in buttons[1][0].callback_data

    @patch('bot.telegram_notifier.tmdb_get')
    def test_add_command_no_args(self, mock_tmdb):
        from bot.telegram_notifier import add_command

        mock_update = MagicMock()
        mock_update.message = AsyncMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()
        mock_context.args = []

        asyncio.get_event_loop().run_until_complete(
            add_command(mock_update, mock_context)
        )

        text = mock_update.message.reply_text.call_args[0][0]
        assert 'Usage' in text


class TestSearchCommand(unittest.TestCase):
    """Test /search command returns recommendations."""

    @patch('bot.telegram_notifier.tmdb_get')
    @patch('bot.telegram_notifier.sqlite3')
    def test_search_sends_recs(self, mock_sqlite3, mock_tmdb):
        from bot.telegram_notifier import search_command

        mock_conn = MagicMock()
        mock_sqlite3.connect.return_value = mock_conn
        mock_sqlite3.Row = sqlite3.Row
        mock_conn.execute.return_value.fetchone.return_value = None  # not in library

        # First call: search, second: recs
        mock_tmdb.side_effect = [
            {'results': [{'id': 550, 'media_type': 'movie', 'title': 'Fight Club'}]},
            {'results': [
                {'id': 680, 'title': 'Pulp Fiction', 'original_title': 'Pulp Fiction',
                 'poster_path': '/pf.jpg', 'release_date': '1994-10-14', 'media_type': 'movie'},
            ]},
        ]

        mock_update = MagicMock()
        mock_update.message = AsyncMock()
        mock_update.message.reply_photo = AsyncMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()
        mock_context.args = ['fight', 'club']

        asyncio.get_event_loop().run_until_complete(
            search_command(mock_update, mock_context)
        )

        mock_update.message.reply_photo.assert_called_once()
        assert 'Pulp Fiction' in mock_update.message.reply_photo.call_args.kwargs['caption']


class TestMystatsCommand(unittest.TestCase):
    """Test /mystats returns library statistics."""

    @patch('bot.telegram_notifier.sqlite3')
    def test_mystats_shows_counts(self, mock_sqlite3):
        from bot.telegram_notifier import mystats_command

        mock_conn = MagicMock()
        mock_sqlite3.connect.return_value = mock_conn
        mock_sqlite3.Row = sqlite3.Row

        # Each execute() call returns a fresh cursor mock
        cursor_total = MagicMock()
        cursor_total.fetchone.return_value = (15,)
        cursor_by_type = MagicMock()
        cursor_by_type.fetchall.return_value = [
            {'tmdb_type': 'movie', 'cnt': 10},
            {'tmdb_type': 'tv', 'cnt': 5},
        ]
        cursor_episodes = MagicMock()
        cursor_episodes.fetchone.return_value = (42,)
        cursor_recs = MagicMock()
        cursor_recs.fetchone.return_value = (7,)

        mock_conn.execute.side_effect = [cursor_total, cursor_by_type, cursor_episodes, cursor_recs]

        mock_update = MagicMock()
        mock_update.message = AsyncMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()

        asyncio.get_event_loop().run_until_complete(
            mystats_command(mock_update, mock_context)
        )

        text = mock_update.message.reply_text.call_args[0][0]
        assert 'Stats' in text
        assert '15' in text


class TestUpcomingCommand(unittest.TestCase):
    """Test /upcoming command returns air date info."""

    @patch('bot.telegram_notifier.tmdb_get')
    def test_upcoming_tv_show(self, mock_tmdb):
        from bot.telegram_notifier import upcoming_command

        mock_tmdb.side_effect = [
            # search
            {'results': [{'id': 1396, 'media_type': 'tv', 'name': 'Breaking Bad'}]},
            # detail
            {
                'name': 'Breaking Bad', 'status': 'Ended',
                'number_of_seasons': 5,
                'next_episode_to_air': None,
                'seasons': [{'season_number': 5, 'air_date': '2013-08-11'}],
            },
        ]

        mock_update = MagicMock()
        mock_update.message = AsyncMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()
        mock_context.args = ['breaking', 'bad']

        asyncio.get_event_loop().run_until_complete(
            upcoming_command(mock_update, mock_context)
        )

        text = mock_update.message.reply_text.call_args[0][0]
        assert 'Breaking Bad' in text
        assert 'Ended' in text


class TestHelpListsAllCommands(unittest.TestCase):
    """Test /help includes all new commands."""

    def test_help_lists_new_commands(self):
        from bot.telegram_notifier import help_command

        mock_update = MagicMock()
        mock_update.message = AsyncMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()

        asyncio.get_event_loop().run_until_complete(
            help_command(mock_update, mock_context)
        )

        text = mock_update.message.reply_text.call_args[0][0]
        for cmd in ['/start', '/recommendations', '/add', '/search', '/upcoming', '/similar', '/mystats', '/help']:
            assert cmd in text, f"Missing {cmd} in help text"


if __name__ == "__main__":
    unittest.main()
