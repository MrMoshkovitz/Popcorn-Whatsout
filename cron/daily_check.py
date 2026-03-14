"""Daily cron orchestrator for Popcorn.

Runs 5 phases sequentially:
1. Check new seasons
2. Refresh streaming availability
3. Generate recommendations (Monday only)
4. Timeout stale disambiguations
5. Error check + admin alert
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import logging
import time
import asyncio
import sqlite3
from datetime import datetime, timedelta

from config import DB_PATH, TELEGRAM_ADMIN_CHAT_ID, DISAMBIGUATION_TIMEOUT_HOURS
from db.migrate import apply_migrations

# Set up dual logging: stdout + file
log_file = os.path.join(os.path.dirname(__file__), '..', 'logs', 'cron.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file),
    ]
)


def _run_phase_1_new_seasons(consecutive_errors):
    """Phase 1: Check for new seasons of tracked series."""
    logging.info("Phase 1: Checking new seasons...")
    phase_start = time.time()
    try:
        from engine.new_season_checker import check_new_seasons
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            alerts = check_new_seasons(conn)
            if alerts:
                from bot.telegram_notifier import send_new_season_alert, bot
                chat_id = _get_chat_id()
                if bot and chat_id:
                    for alert in alerts:
                        title_name = alert.get('title_he') or alert.get('title_en') or 'Unknown'
                        try:
                            asyncio.run(send_new_season_alert(
                                bot, chat_id,
                                title_name, alert['new_season'],
                                tmdb_id=alert.get('tmdb_id')
                            ))
                        except Exception as e:
                            logging.error(f"Phase 1: Failed to send alert for {title_name}: {e}")
            logging.info(f"Phase 1 complete: {len(alerts)} new seasons found ({time.time() - phase_start:.1f}s)")
        finally:
            conn.close()
    except Exception as e:
        consecutive_errors += 1
        logging.error(f"Phase 1 failed: {e}")
    return consecutive_errors


def _run_phase_2_availability(consecutive_errors):
    """Phase 2: Refresh streaming availability for all titles."""
    logging.info("Phase 2: Refreshing streaming availability...")
    phase_start = time.time()
    try:
        from engine.availability import update_all_availability
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            stats = update_all_availability(conn)
            logging.info(
                f"Phase 2 complete: {stats['total_titles']} titles refreshed, "
                f"{stats['total_providers']} providers found ({time.time() - phase_start:.1f}s)"
            )
        finally:
            conn.close()
    except Exception as e:
        consecutive_errors += 1
        logging.error(f"Phase 2 failed: {e}")
    return consecutive_errors


def _run_phase_3_recommendations(consecutive_errors):
    """Phase 3: Generate recommendations (Monday only)."""
    if datetime.today().weekday() != 0:
        logging.info("Phase 3: Skipping recommendations - not Monday")
        return consecutive_errors

    logging.info("Phase 3: Generating recommendations...")
    phase_start = time.time()
    try:
        from engine.recommendations import generate_all_recommendations
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            stats = generate_all_recommendations(conn)
            logging.info(
                f"Phase 3 complete: {stats['total_titles']} titles processed, "
                f"{stats['total_recs']} recommendations generated ({time.time() - phase_start:.1f}s)"
            )
        finally:
            conn.close()
    except Exception as e:
        consecutive_errors += 1
        logging.error(f"Phase 3 failed: {e}")
    return consecutive_errors


def _run_phase_4_disambiguation(consecutive_errors):
    """Phase 4: Auto-resolve stale disambiguation entries (>48h)."""
    logging.info("Phase 4: Cleaning up stale disambiguations...")
    phase_start = time.time()
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            cutoff = datetime.now() - timedelta(hours=DISAMBIGUATION_TIMEOUT_HOURS)
            cutoff_str = cutoff.strftime('%Y-%m-%d %H:%M:%S')
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM titles WHERE match_status = 'review' AND created_at < ?",
                (cutoff_str,)
            )
            stale = cursor.fetchall()
            for row in stale:
                cursor.execute(
                    "UPDATE titles SET match_status = 'auto' WHERE id = ?",
                    (row['id'],)
                )
            conn.commit()
            logging.info(f"Phase 4 complete: {len(stale)} stale entries resolved ({time.time() - phase_start:.1f}s)")
        finally:
            conn.close()
    except Exception as e:
        consecutive_errors += 1
        logging.error(f"Phase 4 failed: {e}")
    return consecutive_errors


def _run_phase_5_error_check(consecutive_errors):
    """Phase 5: Send admin alert if too many errors occurred."""
    logging.info("Phase 5: Error check...")
    if consecutive_errors >= 3:
        error_msg = f"{consecutive_errors} consecutive errors during daily check"
        logging.warning(f"Admin alert: {error_msg}")
        try:
            from bot.telegram_notifier import send_admin_alert, bot
            chat_id = _get_chat_id()
            if bot and chat_id:
                asyncio.run(send_admin_alert(bot, chat_id, error_msg))
        except Exception as e:
            logging.error(f"Phase 5: Failed to send admin alert: {e}")
    else:
        logging.info(f"Phase 5 complete: {consecutive_errors} errors (below threshold)")


def _get_chat_id():
    """Get Telegram chat ID from DB settings, falling back to env var."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?", ('telegram_chat_id',)
            ).fetchone()
            if row and row['value']:
                return row['value']
        finally:
            conn.close()
    except Exception:
        pass
    return TELEGRAM_ADMIN_CHAT_ID


def daily_check():
    """Run all 5 daily check phases."""
    start = time.time()
    logging.info("=" * 50)
    logging.info("Daily check started")
    logging.info("=" * 50)

    # Apply pending migrations before running phases
    try:
        apply_migrations(DB_PATH)
    except Exception as e:
        logging.error(f"Migration failed: {e}")

    consecutive_errors = 0
    consecutive_errors = _run_phase_1_new_seasons(consecutive_errors)
    consecutive_errors = _run_phase_2_availability(consecutive_errors)
    consecutive_errors = _run_phase_3_recommendations(consecutive_errors)
    consecutive_errors = _run_phase_4_disambiguation(consecutive_errors)
    _run_phase_5_error_check(consecutive_errors)

    logging.info(f"Daily check completed in {time.time() - start:.1f}s")


if __name__ == '__main__':
    daily_check()
