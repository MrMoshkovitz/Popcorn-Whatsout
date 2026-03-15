import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import logging
import sqlite3
from datetime import datetime

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes
import telegram.error

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_CHAT_ID, DB_PATH
from ingestion.tmdb_api import tmdb_get

logger = logging.getLogger(__name__)

bot = Bot(token=TELEGRAM_BOT_TOKEN) if TELEGRAM_BOT_TOKEN else None


async def send_new_season_alert(bot, chat_id, title_name, season_number, provider_name=None, tmdb_id=None, poster_path=None):
    """Send new season notification with poster photo + inline keyboard."""
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
        if poster_path:
            try:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=f"https://image.tmdb.org/t/p/w300{poster_path}",
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
                return
            except telegram.error.TelegramError:
                pass
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
    except telegram.error.TelegramError as e:
        logger.error(f"Failed to send new season alert: {e}")


async def send_recommendation(bot, chat_id, source_title, rec_titles, tmdb_id=None, poster_path=None):
    """Send recommendation notification with optional poster."""
    rec_list = "\n".join(f"- {t}" for t in rec_titles)
    text = f"<b>New Recommendations</b>\nBased on <i>{source_title}</i>, you might like:\n{rec_list}"

    try:
        if poster_path:
            try:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=f"https://image.tmdb.org/t/p/w300{poster_path}",
                    caption=text,
                    parse_mode="HTML"
                )
                return
            except telegram.error.TelegramError:
                pass
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


async def send_weekly_digest(bot, chat_id, stats):
    """Send weekly digest with summary stats."""
    text = "<b>\U0001f37f Weekly Popcorn Digest</b>\n\n"

    if stats.get('new_recs'):
        text += f"<b>New recommendations:</b> {stats['new_recs']}\n"
    if stats.get('coming_soon'):
        text += f"<b>Coming soon:</b> {stats['coming_soon']} titles\n"
    if stats.get('new_titles'):
        text += f"<b>Added this week:</b> {stats['new_titles']} titles\n"

    if not stats.get('new_recs') and not stats.get('coming_soon') and not stats.get('new_titles'):
        text += "No new activity this week. Check your dashboard for recommendations!"

    text += "\n\U0001f449 Open your Popcorn dashboard for details."

    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML"
        )
    except telegram.error.TelegramError as e:
        logger.error(f"Failed to send weekly digest: {e}")


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


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start — store chat_id for notifications."""
    chat_id = str(update.effective_chat.id)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ('telegram_chat_id', chat_id)
        )
        conn.commit()
    finally:
        conn.close()
    await update.message.reply_text(
        "\U0001f37f Welcome to Popcorn! You're connected. I'll notify you about new seasons and recommendations."
    )


async def recommendations_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /recommendations — show top unseen recommendations with posters and streaming info."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        recs = conn.execute(
            "SELECT r.recommended_title, r.poster_path, r.recommended_tmdb_id, r.recommended_type, "
            "GROUP_CONCAT(DISTINCT sa.provider_name) as providers "
            "FROM recommendations r "
            "LEFT JOIN streaming_availability sa "
            "  ON sa.tmdb_id = r.recommended_tmdb_id AND sa.tmdb_type = r.recommended_type "
            "WHERE r.status = 'unseen' "
            "GROUP BY r.id "
            "ORDER BY r.created_at DESC LIMIT 5"
        ).fetchall()
        if recs:
            for r in recs:
                title = r['recommended_title']
                providers = r['providers']
                caption = f"\U0001f3ac {title}"
                if providers:
                    caption += f"\n\U0001f4fa Available on: {providers}"
                if r['poster_path']:
                    try:
                        await update.message.reply_photo(
                            photo=f"https://image.tmdb.org/t/p/w200{r['poster_path']}",
                            caption=caption
                        )
                        continue
                    except telegram.error.TelegramError:
                        pass
                await update.message.reply_text(caption)
        else:
            await update.message.reply_text(
                "No recommendations yet. Upload your Netflix history on the dashboard!"
            )
    finally:
        conn.close()


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _tmdb_search(query):
    """Search TMDB for a title, return top result and media_type."""
    data = tmdb_get('/search/multi', {'query': query, 'language': 'en-US'})
    if not data:
        return None, None
    for r in data.get('results', []):
        if r.get('media_type') in ('movie', 'tv'):
            return r, r['media_type']
    return None, None


async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /add <title> — search TMDB and add to library via inline keyboard."""
    try:
        if not context.args:
            await update.message.reply_text("Usage: /add <title name>\nExample: /add Need for Speed")
            return

        query = ' '.join(context.args)
        print(f"[BOT] /add received: {query}")
        data = tmdb_get('/search/multi', {'query': query, 'language': 'en-US'})
        if not data or not data.get('results'):
            await update.message.reply_text(f"No results found for '{query}'.")
            return

        buttons = []
        for r in data['results'][:3]:
            if r.get('media_type') not in ('movie', 'tv'):
                continue
            name = r.get('title') or r.get('name', 'Unknown')
            year = (r.get('release_date') or r.get('first_air_date') or '')[:4]
            label = f"{name} ({year}) [{r['media_type'].upper()}]" if year else f"{name} [{r['media_type'].upper()}]"
            buttons.append([InlineKeyboardButton(label, callback_data=f"add_{r['id']}_{r['media_type']}")])

        if not buttons:
            await update.message.reply_text(f"No movie/TV results for '{query}'.")
            return

        await update.message.reply_text(
            f"Results for '<b>{query}</b>' \u2014 tap to add:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        print(f"[BOT] /add ERROR: {e}")
        import traceback; traceback.print_exc()
        await update.message.reply_text(f"Error: {e}")


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /search <title> — find recommendations based on a title."""
    try:
        if not context.args:
            await update.message.reply_text("Usage: /search <title name>")
            return

        query = ' '.join(context.args)
        print(f"[BOT] /search received: {query}")
        result, media_type = _tmdb_search(query)
        if not result:
            await update.message.reply_text(f"No results found for '{query}'.")
            return

        tmdb_id = result['id']
        recs_data = tmdb_get(f'/{media_type}/{tmdb_id}/recommendations', {'language': 'en-US'})
        if not recs_data or not recs_data.get('results'):
            name = result.get('title') or result.get('name')
            await update.message.reply_text(f"No recommendations found for '{name}'.")
            return

        conn = _get_db()
        try:
            sent = 0
            for rec in recs_data['results'][:5]:
                rec_id = rec['id']
                rec_type = rec.get('media_type', media_type)
                existing = conn.execute(
                    "SELECT 1 FROM titles WHERE tmdb_id = ? AND tmdb_type = ?",
                    (rec_id, rec_type)
                ).fetchone()

                name = rec.get('original_title') or rec.get('original_name') or rec.get('title') or rec.get('name', '')
                year = (rec.get('release_date') or rec.get('first_air_date') or '')[:4]
                watched_tag = " (in library)" if existing else ""

                providers = conn.execute(
                    "SELECT GROUP_CONCAT(DISTINCT provider_name) as p FROM streaming_availability WHERE tmdb_id = ? AND tmdb_type = ?",
                    (rec_id, rec_type)
                ).fetchone()
                prov_str = providers['p'] if providers and providers['p'] else None

                caption = f"\U0001f3ac {name}"
                if year:
                    caption += f" ({year})"
                caption += watched_tag
                if prov_str:
                    caption += f"\n\U0001f4fa {prov_str}"

                poster = rec.get('poster_path')
                if poster:
                    try:
                        await update.message.reply_photo(
                            photo=f"https://image.tmdb.org/t/p/w200{poster}",
                            caption=caption
                        )
                        sent += 1
                        continue
                    except telegram.error.TelegramError:
                        pass
                await update.message.reply_text(caption)
                sent += 1

            if sent == 0:
                await update.message.reply_text("All recommendations are already in your library!")
        finally:
            conn.close()
    except Exception as e:
        print(f"[BOT] /search ERROR: {e}")
        import traceback; traceback.print_exc()
        await update.message.reply_text(f"Error: {e}")


async def upcoming_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /upcoming <title> — check next season/sequel info."""
    try:
        if not context.args:
            await update.message.reply_text("Usage: /upcoming <title name>\nExample: /upcoming Stranger Things")
            return

        query = ' '.join(context.args)
        print(f"[BOT] /upcoming received: {query}")
        result, media_type = _tmdb_search(query)
        if not result:
            await update.message.reply_text(f"No results found for '{query}'.")
            return

        tmdb_id = result['id']
        name = result.get('title') or result.get('name')

        if media_type == 'tv':
            detail = tmdb_get(f'/tv/{tmdb_id}', {'language': 'en-US'})
            if not detail:
                await update.message.reply_text(f"Couldn't fetch details for '{name}'.")
                return

            status = detail.get('status', 'Unknown')
            seasons = detail.get('number_of_seasons', 0)
            next_ep = detail.get('next_episode_to_air')

            text = f"<b>{name}</b>\nStatus: {status}\nSeasons: {seasons}"
            if next_ep:
                air = next_ep.get('air_date', 'TBA')
                ep_name = next_ep.get('name', '')
                text += f"\n\nNext episode: S{next_ep.get('season_number', '?')}E{next_ep.get('episode_number', '?')}"
                if ep_name:
                    text += f" \u2014 {ep_name}"
                text += f"\nAir date: {air}"
            elif status == 'Returning Series':
                last_season = None
                for s in detail.get('seasons', []):
                    if s.get('season_number', 0) > 0:
                        last_season = s
                if last_season and last_season.get('air_date'):
                    text += f"\n\nLast season aired: {last_season['air_date']}"
                text += "\nNo next episode scheduled yet."
            else:
                text += f"\n\nNo upcoming episodes."

            await update.message.reply_text(text, parse_mode="HTML")
        else:
            detail = tmdb_get(f'/movie/{tmdb_id}', {'language': 'en-US'})
            if not detail:
                await update.message.reply_text(f"Couldn't fetch details for '{name}'.")
                return

            collection = detail.get('belongs_to_collection')
            if not collection:
                await update.message.reply_text(f"<b>{name}</b>\nNo collection/franchise found.", parse_mode="HTML")
                return

            coll_data = tmdb_get(f"/collection/{collection['id']}", {'language': 'en-US'})
            if not coll_data:
                await update.message.reply_text(f"<b>{name}</b>\nPart of '{collection.get('name')}' but couldn't fetch details.", parse_mode="HTML")
                return

            text = f"<b>{name}</b>\nCollection: {coll_data.get('name', '')}\n"
            for part in coll_data.get('parts', []):
                release = part.get('release_date', '')
                status_tag = ""
                if not release:
                    status_tag = " [TBA]"
                elif release > datetime.now().strftime('%Y-%m-%d'):
                    status_tag = f" [Upcoming: {release}]"
                text += f"\n- {part.get('title', '?')}{status_tag}"

            await update.message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        print(f"[BOT] /upcoming ERROR: {e}")
        import traceback; traceback.print_exc()
        await update.message.reply_text(f"Error: {e}")


async def similar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /similar <title> — recommendations + similar, scored by genre overlap."""
    try:
        if not context.args:
            await update.message.reply_text("Usage: /similar <title name>")
            return

        query = ' '.join(context.args)
        print(f"[BOT] /similar received: {query}")
        result, media_type = _tmdb_search(query)
        if not result:
            await update.message.reply_text(f"No results found for '{query}'.")
            return

        tmdb_id = result['id']
        name = result.get('title') or result.get('name')

        conn = _get_db()
        try:
            titles = conn.execute("SELECT tmdb_id, tmdb_type FROM titles").fetchall()
        finally:
            conn.close()

        recs = tmdb_get(f'/{media_type}/{tmdb_id}/recommendations', {'language': 'en-US'})
        similar = tmdb_get(f'/{media_type}/{tmdb_id}/similar', {'language': 'en-US'})

        candidates = {}
        source_genres = set(result.get('genre_ids', []))

        for source_list in [recs, similar]:
            if not source_list:
                continue
            for r in source_list.get('results', []):
                rid = r['id']
                if rid == tmdb_id or rid in candidates:
                    continue
                r_genres = set(r.get('genre_ids', []))
                overlap = len(source_genres & r_genres)
                score = overlap * 2 + r.get('vote_average', 0) / 10
                candidates[rid] = {'result': r, 'score': score}

        if not candidates:
            await update.message.reply_text(f"No similar titles found for '{name}'.")
            return

        sorted_recs = sorted(candidates.values(), key=lambda x: x['score'], reverse=True)[:5]
        for item in sorted_recs:
            r = item['result']
            rec_name = r.get('original_title') or r.get('original_name') or r.get('title') or r.get('name', '')
            year = (r.get('release_date') or r.get('first_air_date') or '')[:4]
            caption = f"\U0001f3ac {rec_name}"
            if year:
                caption += f" ({year})"
            poster = r.get('poster_path')
            if poster:
                try:
                    await update.message.reply_photo(
                        photo=f"https://image.tmdb.org/t/p/w200{poster}",
                        caption=caption
                    )
                    continue
                except telegram.error.TelegramError:
                    pass
            await update.message.reply_text(caption)
    except Exception as e:
        print(f"[BOT] /similar ERROR: {e}")
        import traceback; traceback.print_exc()
        await update.message.reply_text(f"Error: {e}")


async def mystats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /mystats — show library statistics."""
    try:
        print("[BOT] /mystats received")
        conn = _get_db()
        try:
            total = conn.execute("SELECT COUNT(*) FROM titles").fetchone()[0]
            by_type = conn.execute(
                "SELECT tmdb_type, COUNT(*) as cnt FROM titles GROUP BY tmdb_type"
            ).fetchall()
            episodes = conn.execute("SELECT COUNT(*) FROM watch_history").fetchone()[0]
            recs = conn.execute("SELECT COUNT(*) FROM recommendations WHERE status = 'unseen'").fetchone()[0]

            text = "\U0001f4ca <b>Your Popcorn Stats</b>\n\n"
            text += f"Total titles: {total}\n"
            for row in by_type:
                text += f"  {row['tmdb_type'].upper()}: {row['cnt']}\n"
            text += f"\nWatch history entries: {episodes}"
            text += f"\nPending recommendations: {recs}"

            await update.message.reply_text(text, parse_mode="HTML")
        finally:
            conn.close()
    except Exception as e:
        print(f"[BOT] /mystats ERROR: {e}")
        import traceback; traceback.print_exc()
        await update.message.reply_text(f"Error: {e}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help — list available commands."""
    await update.message.reply_text(
        "\U0001f37f Popcorn Bot Commands:\n\n"
        "/start - Connect this chat for notifications\n"
        "/recommendations - Show top 5 unseen recommendations\n"
        "/add <title> - Add a title to your library\n"
        "/search <title> - Get recommendations based on a title\n"
        "/upcoming <title> - Check next season/sequel info\n"
        "/similar <title> - Find similar titles with genre matching\n"
        "/mystats - View your library statistics\n"
        "/help - Show this help message"
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all inline keyboard callbacks."""
    query = update.callback_query
    await query.answer()
    data = query.data

    try:
        if data.startswith("add_"):
            parts = data.split("_")
            tmdb_id = int(parts[1])
            tmdb_type = parts[2]
            # Fetch details for both languages
            details_he = tmdb_get(f'/{tmdb_type}/{tmdb_id}', {'language': 'he-IL'})
            details_en = tmdb_get(f'/{tmdb_type}/{tmdb_id}', {'language': 'en-US'})
            title_he = (details_he or {}).get('title') or (details_he or {}).get('name')
            title_en = (details_en or {}).get('title') or (details_en or {}).get('name')
            poster = (details_he or details_en or {}).get('poster_path')
            original_language = (details_en or details_he or {}).get('original_language')

            conn = _get_db()
            try:
                conn.execute(
                    """INSERT OR REPLACE INTO titles
                       (tmdb_id, tmdb_type, title_he, title_en, poster_path, original_language,
                        match_status, confidence, source, user_tag)
                       VALUES (?, ?, ?, ?, ?, ?, 'manual', 1.0, 'manual', 'both')""",
                    (tmdb_id, tmdb_type, title_he, title_en, poster, original_language)
                )
                if tmdb_type == 'tv':
                    title_id = conn.execute(
                        "SELECT id FROM titles WHERE tmdb_id = ? AND tmdb_type = ?",
                        (tmdb_id, tmdb_type)
                    ).fetchone()['id']
                    num_seasons = (details_en or details_he or {}).get('number_of_seasons', 1)
                    total_episodes = (details_en or details_he or {}).get('number_of_episodes')
                    conn.execute(
                        """INSERT OR REPLACE INTO series_tracking
                           (title_id, tmdb_id, max_watched_season, total_seasons_tmdb,
                            total_episodes_tmdb, status)
                           VALUES (?, ?, ?, ?, ?, 'watching')""",
                        (title_id, tmdb_id, num_seasons, num_seasons, total_episodes)
                    )
                conn.commit()
            finally:
                conn.close()
            display = title_en if original_language != 'he' else (title_he or title_en)
            await query.edit_message_text(f"Added '{display}' to your library!")

        elif data.startswith("watched_"):
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
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("recommendations", recommendations_command))
    application.add_handler(CommandHandler("add", add_command))
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(CommandHandler("upcoming", upcoming_command))
    application.add_handler(CommandHandler("similar", similar_command))
    application.add_handler(CommandHandler("mystats", mystats_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_error_handler(error_handler)
    application.run_polling()


if __name__ == "__main__":
    run_bot()
