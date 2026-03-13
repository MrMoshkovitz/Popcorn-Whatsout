import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import logging
import sqlite3
from datetime import datetime

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes
import telegram.error

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_CHAT_ID, DB_PATH

logger = logging.getLogger(__name__)

bot = Bot(token=TELEGRAM_BOT_TOKEN) if TELEGRAM_BOT_TOKEN else None


async def send_new_season_alert(bot, chat_id, title_name, season_number, provider_name=None, tmdb_id=None):
    """Send new season notification with watched/remind inline keyboard."""
    text = f"<b>New Season!</b>\n{title_name} Season {season_number} is now available"
    if provider_name:
        text += f" on {provider_name}"

    keyboard = None
    if tmdb_id:
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Mark as watched", callback_data=f"watched_{tmdb_id}"),
                InlineKeyboardButton("Remind later", callback_data=f"remind_{tmdb_id}")
            ]
        ])

    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
    except telegram.error.TelegramError as e:
        logger.error(f"Failed to send new season alert: {e}")


async def send_recommendation(bot, chat_id, source_title, rec_titles, tmdb_id=None):
    """Send recommendation notification."""
    rec_list = "\n".join(f"- {t}" for t in rec_titles)
    text = f"<b>New Recommendation</b>\nBased on <i>{source_title}</i>, you might like:\n{rec_list}"

    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML"
        )
    except telegram.error.TelegramError as e:
        logger.error(f"Failed to send recommendation: {e}")


async def send_disambiguation(bot, chat_id, raw_title, candidates, title_id):
    """Send disambiguation with top 3 candidates as inline keyboard."""
    text = f"<b>Which one?</b>\nWhich '{raw_title}' did you watch?"

    buttons = []
    for candidate in candidates[:3]:
        tmdb_id = candidate.get("id") or candidate.get("tmdb_id")
        name = candidate.get("title") or candidate.get("name", "Unknown")
        year = ""
        release = candidate.get("release_date") or candidate.get("first_air_date", "")
        if release:
            year = f" ({release[:4]})"
        buttons.append([
            InlineKeyboardButton(
                text=f"{name}{year}",
                callback_data=f"disambig_{title_id}_{tmdb_id}"
            )
        ])

    keyboard = InlineKeyboardMarkup(buttons) if buttons else None

    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
    except telegram.error.TelegramError as e:
        logger.error(f"Failed to send disambiguation: {e}")


async def send_admin_alert(bot, chat_id, error_message):
    """Send error alert to admin."""
    text = f"<b>Admin Alert</b>\n{error_message}\nTimestamp: {datetime.now().isoformat()}"

    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML"
        )
    except telegram.error.TelegramError as e:
        logger.error(f"Failed to send admin alert: {e}")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all inline keyboard callbacks."""
    query = update.callback_query
    await query.answer()
    data = query.data

    try:
        if data.startswith("watched_"):
            tmdb_id = int(data.split("_")[1])
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE series_tracking SET max_watched_season = total_seasons_tmdb "
                    "WHERE tmdb_id = ?",
                    (tmdb_id,)
                )
                conn.commit()
            finally:
                conn.close()
            await query.edit_message_text("Marked as watched!")

        elif data.startswith("remind_"):
            await query.edit_message_text("Got it! Check the Coming Soon tab when you're ready.")

        elif data.startswith("disambig_"):
            parts = data.split("_")
            title_id = int(parts[1])
            tmdb_id = int(parts[2])
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE titles SET tmdb_id = ?, match_status = 'auto' WHERE id = ?",
                    (tmdb_id, title_id)
                )
                conn.commit()
            finally:
                conn.close()
            await query.edit_message_text("Match confirmed!")

    except Exception as e:
        logger.error(f"Callback handler error: {e}")
        await query.edit_message_text(f"Error processing your choice. Please try again from the dashboard.")


async def error_handler(update, context):
    """Log errors from the bot."""
    logger.error(f"Update {update} caused error {context.error}")


def run_bot():
    """Start the bot in long-polling mode."""
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("No TELEGRAM_BOT_TOKEN set, bot not starting")
        return
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_error_handler(error_handler)
    application.run_polling()


if __name__ == "__main__":
    run_bot()
