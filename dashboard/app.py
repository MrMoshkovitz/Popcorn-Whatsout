import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
import sqlite3
import logging
import tempfile
import os as _os
from datetime import datetime, timedelta
from config import DB_PATH
from ingestion.csv_parser import parse_netflix_csv
from ingestion.tmdb_matcher import match_entries
from ingestion.tmdb_api import tmdb_get
from engine.recommendations import generate_recommendations, generate_all_recommendations
from db.migrate import apply_migrations

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = _os.urandom(24)

# Apply pending database migrations on startup
try:
    apply_migrations(DB_PATH)
except Exception as e:
    logger.error(f"Migration failed on startup: {e}")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_review_count():
    conn = get_db()
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM titles WHERE match_status = ?", ('review',)
        ).fetchone()[0]
        return count
    finally:
        conn.close()


def get_active_tag():
    """Get active user tag filter from query string."""
    tag = request.args.get('tag', 'all')
    if tag not in ('me', 'wife', 'all'):
        tag = 'all'
    return tag


def tag_filter_sql(table_alias='t'):
    """Return SQL WHERE clause and params for user_tag filtering."""
    tag = get_active_tag()
    if tag == 'all':
        return '', ()
    return f" AND {table_alias}.user_tag IN (?, 'both')", (tag,)


@app.context_processor
def inject_tag():
    """Make active_tag available in all templates."""
    return {'active_tag': get_active_tag()}


@app.route('/')
def index():
    return redirect(url_for('watch_next'))


@app.route('/watch-next')
def watch_next():
    conn = get_db()
    try:
        tag_sql, tag_params = tag_filter_sql('t')
        recommendations = conn.execute("""
            SELECT r.id, r.recommended_title, r.poster_path, r.recommended_tmdb_id,
                   r.recommended_type, t.title_he, t.title_en,
                   COALESCE(t.title_he, t.title_en) AS source_title
            FROM recommendations r
            JOIN titles t ON r.source_title_id = t.id
            WHERE r.status = ?""" + tag_sql + """
            ORDER BY r.created_at DESC
        """, ('unseen',) + tag_params).fetchall()

        # Attach streaming providers to each recommendation
        recs_with_providers = []
        for rec in recommendations:
            providers = conn.execute("""
                SELECT provider_name, provider_logo_path, monetization_type
                FROM streaming_availability
                WHERE tmdb_id = ? AND tmdb_type = ?
            """, (rec['recommended_tmdb_id'], rec['recommended_type'])).fetchall()
            recs_with_providers.append({
                'id': rec['id'],
                'recommended_title': rec['recommended_title'],
                'poster_path': rec['poster_path'],
                'source_title': rec['source_title'],
                'providers': providers,
            })

        # Season gaps: series where user hasn't finished all available seasons
        continue_rows = conn.execute("""
            SELECT t.id, COALESCE(t.title_he, t.title_en) AS title,
                   t.poster_path, t.tmdb_id, t.tmdb_type,
                   st.max_watched_season, st.total_seasons_tmdb
            FROM series_tracking st
            JOIN titles t ON st.title_id = t.id
            WHERE st.status = ? AND st.total_seasons_tmdb > st.max_watched_season""" + tag_sql + """
            ORDER BY t.title_en
        """, ('watching',) + tag_params).fetchall()

        continue_watching = []
        for row in continue_rows:
            providers = conn.execute("""
                SELECT provider_name, provider_logo_path, monetization_type
                FROM streaming_availability
                WHERE tmdb_id = ? AND tmdb_type = ?
            """, (row['tmdb_id'], row['tmdb_type'])).fetchall()
            next_season = (row['max_watched_season'] or 0) + 1
            continue_watching.append({
                'title': row['title'],
                'poster_path': row['poster_path'],
                'next_season': next_season,
                'total_seasons': row['total_seasons_tmdb'] or 0,
                'providers': providers,
            })

        return render_template('watch_next.html',
                               recommendations=recs_with_providers,
                               continue_watching=continue_watching,
                               review_count=get_review_count())
    finally:
        conn.close()


@app.route('/coming-soon')
def coming_soon():
    conn = get_db()
    try:
        tag_sql, tag_params = tag_filter_sql('t')
        alerts_rows = conn.execute("""
            SELECT t.id, COALESCE(t.title_he, t.title_en) AS title,
                   t.poster_path, t.tmdb_id, t.tmdb_type,
                   st.max_watched_season, st.total_seasons_tmdb
            FROM series_tracking st
            JOIN titles t ON st.title_id = t.id
            WHERE st.status = ? AND st.total_seasons_tmdb > st.max_watched_season""" + tag_sql + """
            ORDER BY t.title_en
        """, ('watching',) + tag_params).fetchall()

        alerts = []
        for row in alerts_rows:
            providers = conn.execute("""
                SELECT provider_name, provider_logo_path, monetization_type
                FROM streaming_availability
                WHERE tmdb_id = ? AND tmdb_type = ?
            """, (row['tmdb_id'], row['tmdb_type'])).fetchall()
            new_season = (row['max_watched_season'] or 0) + 1
            alerts.append({
                'title': row['title'],
                'poster_path': row['poster_path'],
                'new_season': new_season,
                'watched_season': row['max_watched_season'] or 0,
                'total_seasons': row['total_seasons_tmdb'] or 0,
                'providers': providers,
            })

        return render_template('coming_soon.html',
                               alerts=alerts,
                               review_count=get_review_count())
    finally:
        conn.close()


@app.route('/library')
def library():
    conn = get_db()
    try:
        tag_sql, tag_params = tag_filter_sql('t')
        titles = conn.execute("""
            SELECT t.id, t.title_he, t.title_en, t.tmdb_type, t.poster_path,
                   t.user_tag, COUNT(wh.id) AS watch_count,
                   MAX(wh.watch_date) AS last_watched
            FROM titles t
            LEFT JOIN watch_history wh ON t.id = wh.title_id
            WHERE 1=1""" + tag_sql + """
            GROUP BY t.id
            ORDER BY last_watched DESC
        """, tag_params).fetchall()

        return render_template('library.html',
                               titles=titles,
                               review_count=get_review_count())
    finally:
        conn.close()


@app.route('/review')
def review():
    conn = get_db()
    try:
        review_items = conn.execute("""
            SELECT t.id, t.tmdb_id, t.tmdb_type, t.title_he, t.title_en,
                   t.poster_path, t.confidence,
                   wh.raw_csv_title AS raw_title
            FROM titles t
            LEFT JOIN watch_history wh ON t.id = wh.title_id
            WHERE t.match_status = ?
            GROUP BY t.id
            ORDER BY t.confidence ASC
        """, ('review',)).fetchall()

        return render_template('review.html',
                               review_items=review_items,
                               review_count=len(review_items))
    finally:
        conn.close()


@app.route('/upload', methods=['POST'])
def upload():
    conn = get_db()
    try:
        # Check 24h rate limit
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", ('last_upload_date',)
        ).fetchone()
        if row:
            last_upload = datetime.fromisoformat(row['value'])
            if datetime.now() - last_upload < timedelta(hours=24):
                flash('Upload rate limited — please wait 24 hours between uploads.')
                return redirect(url_for('library'))

        # Validate file
        if 'csv_file' not in request.files:
            flash('No file selected.')
            return redirect(url_for('library'))

        file = request.files['csv_file']
        if not file.filename or not file.filename.lower().endswith('.csv'):
            flash('Please upload a .csv file.')
            return redirect(url_for('library'))

        # Save to temp file, parse, match
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.csv')
        try:
            file.save(tmp.name)
            tmp.close()
            entries = parse_netflix_csv(tmp.name)
        finally:
            _os.unlink(tmp.name)

        if not entries:
            flash('No valid entries found in CSV.')
            return redirect(url_for('library'))

        user_tag = request.form.get('user_tag', 'both')
        if user_tag not in ('me', 'wife', 'both'):
            user_tag = 'both'

        stats = match_entries(entries, conn, user_tag=user_tag)

        # Generate recommendations for all matched titles
        try:
            rec_stats = generate_all_recommendations(conn)
            rec_count = rec_stats.get('total_recs', 0)
        except Exception as e:
            logger.warning(f"Recommendation generation failed: {e}")
            rec_count = 0

        # Update last upload timestamp
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ('last_upload_date', datetime.now().isoformat())
        )
        conn.commit()

        flash(f"Upload complete: {stats.get('matched', 0)} matched, "
              f"{stats.get('review', 0)} need review, "
              f"{stats.get('errors', 0)} errors, "
              f"{rec_count} recommendations generated.")
        return redirect(url_for('library'))
    finally:
        conn.close()


@app.route('/search')
def search():
    q = request.args.get('q', '').strip()
    if len(q) < 3:
        return jsonify([])

    results = tmdb_get('/search/multi', {'query': q, 'language': 'he-IL'})
    if not results or not results.get('results'):
        results = tmdb_get('/search/multi', {'query': q, 'language': 'en-US'})

    items = []
    for r in (results or {}).get('results', []):
        if r.get('media_type') not in ('movie', 'tv'):
            continue
        title = r.get('name') or r.get('title', '')
        year = (r.get('first_air_date') or r.get('release_date') or '')[:4]
        item = {
            'tmdb_id': r['id'],
            'media_type': r['media_type'],
            'title': title,
            'year': year,
            'poster_path': r.get('poster_path'),
        }
        if r.get('media_type') == 'tv':
            item['number_of_seasons'] = r.get('number_of_seasons')
        items.append(item)
        if len(items) >= 5:
            break
    return jsonify(items)


@app.route('/add', methods=['POST'])
def add():
    tmdb_id = request.form.get('tmdb_id', type=int)
    tmdb_type = request.form.get('tmdb_type', '')
    if not tmdb_id or tmdb_type not in ('movie', 'tv'):
        flash('Invalid title selection.')
        return redirect(url_for('library'))

    user_tag = request.form.get('user_tag', 'both')
    if user_tag not in ('me', 'wife', 'both'):
        user_tag = 'both'

    details_he = tmdb_get(f'/{tmdb_type}/{tmdb_id}', {'language': 'he-IL'})
    details_en = tmdb_get(f'/{tmdb_type}/{tmdb_id}', {'language': 'en-US'})

    conn = get_db()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO titles
            (tmdb_id, tmdb_type, title_he, title_en, poster_path, match_status, confidence, source, user_tag)
            VALUES (?, ?, ?, ?, ?, 'manual', 1.0, 'manual', ?)
        """, (
            tmdb_id, tmdb_type,
            (details_he or {}).get('title') or (details_he or {}).get('name'),
            (details_en or {}).get('title') or (details_en or {}).get('name'),
            (details_he or details_en or {}).get('poster_path'),
            user_tag,
        ))

        # Get the title_id for recommendation generation
        row = conn.execute(
            "SELECT id FROM titles WHERE tmdb_id = ? AND tmdb_type = ?",
            (tmdb_id, tmdb_type)
        ).fetchone()
        if row is None:
            flash('Failed to add title — please try again.')
            return redirect(url_for('library'))
        title_id = row['id']

        if tmdb_type == 'tv':
            num_seasons = (details_en or details_he or {}).get('number_of_seasons', 1)
            watched_seasons = request.form.get('watched_seasons', type=int)
            if watched_seasons is None or watched_seasons < 0:
                watched_seasons = num_seasons
            watched_seasons = min(watched_seasons, num_seasons)
            conn.execute("""
                INSERT OR REPLACE INTO series_tracking
                (title_id, tmdb_id, max_watched_season, total_seasons_tmdb, status)
                VALUES (?, ?, ?, ?, 'watching')
            """, (title_id, tmdb_id, watched_seasons, num_seasons))

        conn.commit()

        # Generate recommendations for this title
        try:
            generate_recommendations(conn, tmdb_id, tmdb_type, title_id)
        except Exception as e:
            logger.warning(f"Recommendation generation failed for added title: {e}")

        flash('Title added to library.')
    finally:
        conn.close()
    return redirect(url_for('library'))


@app.route('/resolve/<int:title_id>', methods=['POST'])
def resolve(title_id):
    new_tmdb_id = request.form.get('new_tmdb_id', type=int)
    new_tmdb_type = request.form.get('new_tmdb_type', '')

    conn = get_db()
    try:
        if new_tmdb_id and new_tmdb_type in ('movie', 'tv'):
            conn.execute(
                "UPDATE titles SET tmdb_id = ?, tmdb_type = ?, match_status = 'manual', confidence = 1.0 WHERE id = ?",
                (new_tmdb_id, new_tmdb_type, title_id)
            )
        else:
            conn.execute(
                "UPDATE titles SET match_status = 'auto' WHERE id = ?",
                (title_id,)
            )
        conn.commit()
    finally:
        conn.close()
    return redirect(url_for('review'))


@app.route('/dismiss/<int:rec_id>', methods=['POST'])
def dismiss(rec_id):
    conn = get_db()
    try:
        conn.execute(
            "UPDATE recommendations SET status = 'dismissed' WHERE id = ?",
            (rec_id,)
        )
        conn.commit()
    finally:
        conn.close()
    return redirect(url_for('watch_next'))


@app.route('/delete/<int:title_id>', methods=['POST'])
def delete_title(title_id):
    conn = get_db()
    try:
        title = conn.execute(
            "SELECT COALESCE(title_he, title_en) AS name, tmdb_id, tmdb_type FROM titles WHERE id = ?",
            (title_id,)
        ).fetchone()
        if not title:
            flash('Title not found.')
            return redirect(url_for('library'))

        name = title['name']
        conn.execute("DELETE FROM watch_history WHERE title_id = ?", (title_id,))
        conn.execute("DELETE FROM series_tracking WHERE title_id = ?", (title_id,))
        conn.execute("DELETE FROM recommendations WHERE source_title_id = ?", (title_id,))
        conn.execute("DELETE FROM streaming_availability WHERE tmdb_id = ? AND tmdb_type = ?",
                     (title['tmdb_id'], title['tmdb_type']))
        conn.execute("DELETE FROM titles WHERE id = ?", (title_id,))
        conn.commit()
        flash(f'Deleted: {name}')
    finally:
        conn.close()
    return redirect(url_for('library'))


@app.route('/edit/<int:title_id>')
def edit_title(title_id):
    conn = get_db()
    try:
        title = conn.execute("""
            SELECT t.id, t.tmdb_id, t.tmdb_type, t.title_he, t.title_en, t.poster_path,
                   t.user_tag, st.max_watched_season, st.total_seasons_tmdb
            FROM titles t
            LEFT JOIN series_tracking st ON t.id = st.title_id
            WHERE t.id = ?
        """, (title_id,)).fetchone()
        if not title:
            flash('Title not found.')
            return redirect(url_for('library'))
        return render_template('edit.html', title=title, review_count=get_review_count())
    finally:
        conn.close()


@app.route('/edit/<int:title_id>', methods=['POST'])
def edit_title_post(title_id):
    conn = get_db()
    try:
        # Handle TMDB re-match
        new_tmdb_id = request.form.get('new_tmdb_id', type=int)
        new_tmdb_type = request.form.get('new_tmdb_type', '')
        if new_tmdb_id and new_tmdb_type in ('movie', 'tv'):
            details_he = tmdb_get(f'/{new_tmdb_type}/{new_tmdb_id}', {'language': 'he-IL'})
            details_en = tmdb_get(f'/{new_tmdb_type}/{new_tmdb_id}', {'language': 'en-US'})
            conn.execute("""
                UPDATE titles SET tmdb_id = ?, tmdb_type = ?, title_he = ?, title_en = ?,
                       poster_path = ?, match_status = 'manual', confidence = 1.0
                WHERE id = ?
            """, (
                new_tmdb_id, new_tmdb_type,
                (details_he or {}).get('title') or (details_he or {}).get('name'),
                (details_en or {}).get('title') or (details_en or {}).get('name'),
                (details_he or details_en or {}).get('poster_path'),
                title_id,
            ))

        # Handle user tag update
        new_tag = request.form.get('user_tag', '')
        if new_tag in ('me', 'wife', 'both'):
            conn.execute(
                "UPDATE titles SET user_tag = ? WHERE id = ?",
                (new_tag, title_id)
            )

        # Handle watched seasons update for TV
        watched_seasons = request.form.get('watched_seasons', type=int)
        if watched_seasons is not None and watched_seasons >= 0:
            conn.execute(
                "UPDATE series_tracking SET max_watched_season = ? WHERE title_id = ?",
                (watched_seasons, title_id)
            )

        conn.commit()
        flash('Title updated.')
    finally:
        conn.close()
    return redirect(url_for('library'))


if __name__ == '__main__':
    app.run(debug=True, port=5000)
