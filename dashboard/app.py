import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from flask import Flask, render_template, redirect, url_for
import sqlite3
from config import DB_PATH

app = Flask(__name__)


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


@app.route('/')
def index():
    return redirect(url_for('watch_next'))


@app.route('/watch-next')
def watch_next():
    conn = get_db()
    try:
        recommendations = conn.execute("""
            SELECT r.id, r.recommended_title, r.poster_path, r.recommended_tmdb_id,
                   r.recommended_type, t.title_he, t.title_en,
                   COALESCE(t.title_he, t.title_en) AS source_title
            FROM recommendations r
            JOIN titles t ON r.source_title_id = t.id
            WHERE r.status = ?
            ORDER BY r.created_at DESC
        """, ('unseen',)).fetchall()

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

        return render_template('watch_next.html',
                               recommendations=recs_with_providers,
                               review_count=get_review_count())
    finally:
        conn.close()


@app.route('/coming-soon')
def coming_soon():
    conn = get_db()
    try:
        alerts_rows = conn.execute("""
            SELECT t.id, COALESCE(t.title_he, t.title_en) AS title,
                   t.poster_path, t.tmdb_id, t.tmdb_type,
                   st.total_seasons_tmdb AS season_number
            FROM series_tracking st
            JOIN titles t ON st.title_id = t.id
            WHERE st.status = ? AND st.total_seasons_tmdb > st.max_watched_season
            ORDER BY t.title_en
        """, ('watching',)).fetchall()

        alerts = []
        for row in alerts_rows:
            providers = conn.execute("""
                SELECT provider_name, provider_logo_path, monetization_type
                FROM streaming_availability
                WHERE tmdb_id = ? AND tmdb_type = ?
            """, (row['tmdb_id'], row['tmdb_type'])).fetchall()
            alerts.append({
                'title': row['title'],
                'poster_path': row['poster_path'],
                'season_number': row['season_number'],
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
        titles = conn.execute("""
            SELECT t.id, t.title_he, t.title_en, t.tmdb_type, t.poster_path,
                   COUNT(wh.id) AS watch_count,
                   MAX(wh.watch_date) AS last_watched
            FROM titles t
            LEFT JOIN watch_history wh ON t.id = wh.title_id
            GROUP BY t.id
            ORDER BY last_watched DESC
        """).fetchall()

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


if __name__ == '__main__':
    app.run(debug=True, port=5000)
