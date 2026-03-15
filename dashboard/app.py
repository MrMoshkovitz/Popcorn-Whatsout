import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
import json
import sqlite3
import logging
import tempfile
import os as _os
from collections import defaultdict
from datetime import datetime, timedelta
from config import DB_PATH
from ingestion.csv_parser import parse_netflix_csv
from ingestion.tmdb_matcher import match_entries
from ingestion.tmdb_api import tmdb_get
from engine.recommendations import generate_recommendations, generate_all_recommendations, purge_library_recommendations
from engine.taste_scorer import score_all_recommendations
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
def inject_globals():
    """Make active_tag and telegram status available in all templates."""
    telegram_connected = False
    try:
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?", ('telegram_chat_id',)
            ).fetchone()
            telegram_connected = bool(row and row['value'])
        finally:
            conn.close()
    except Exception:
        pass
    return {'active_tag': get_active_tag(), 'telegram_connected': telegram_connected}


@app.route('/')
def index():
    return redirect(url_for('watch_next'))


@app.route('/watch-next')
def watch_next():
    conn = get_db()
    try:
        tag_sql, tag_params = tag_filter_sql('t')

        # Continue Watching — season gaps with enriched data
        continue_rows = conn.execute("""
            SELECT t.id, CASE WHEN t.original_language = 'he' THEN COALESCE(t.title_he, t.title_en) ELSE COALESCE(t.title_en, t.title_he) END AS title,
                   t.poster_path, t.tmdb_id, t.tmdb_type, t.user_tag,
                   t.vote_average, t.overview, t.backdrop_path, t.release_year, t.genres,
                   st.max_watched_season, st.total_seasons_tmdb
            FROM series_tracking st
            JOIN titles t ON st.title_id = t.id
            WHERE st.status = ? AND st.total_seasons_tmdb > st.max_watched_season
              AND st.next_season_air_date IS NOT NULL
              AND st.next_season_air_date <= date('now')""" + tag_sql + """
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
            genres = []
            if row['genres']:
                try:
                    genres = json.loads(row['genres'])
                except (json.JSONDecodeError, TypeError):
                    pass
            continue_watching.append({
                'title': row['title'],
                'poster_path': row['poster_path'],
                'tmdb_id': row['tmdb_id'],
                'tmdb_type': row['tmdb_type'],
                'next_season': next_season,
                'total_seasons': row['total_seasons_tmdb'] or 0,
                'max_watched_season': row['max_watched_season'] or 0,
                'user_tag': row['user_tag'] or 'both',
                'providers': providers,
                'vote_average': row['vote_average'] or 0,
                'overview': row['overview'] or '',
                'backdrop_path': row['backdrop_path'] or '',
                'release_year': row['release_year'] or '',
                'genres': genres,
            })

        # All unseen recommendations with genres + enriched data
        recommendations = conn.execute("""
            SELECT r.id, r.recommended_title, r.poster_path, r.recommended_tmdb_id,
                   r.recommended_type, r.collection_name, r.genres,
                   r.overview AS rec_overview, r.backdrop_path AS rec_backdrop,
                   r.release_year AS rec_year, r.tmdb_recommendation_score AS vote_avg,
                   r.match_score,
                   t.user_tag AS source_tag,
                   CASE WHEN t.original_language = 'he' THEN COALESCE(t.title_he, t.title_en) ELSE COALESCE(t.title_en, t.title_he) END AS source_title
            FROM recommendations r
            JOIN titles t ON r.source_title_id = t.id
            WHERE r.status = ?""" + tag_sql + """
            ORDER BY r.match_score DESC, r.tmdb_recommendation_score DESC
        """, ('unseen',) + tag_params).fetchall()

        # Attach providers and parse genres
        all_providers_set = set()
        all_genres_set = set()
        franchise_catchup = defaultdict(list)  # collection_name -> recs
        movie_recs = []
        tv_recs = []

        for rec in recommendations:
            providers = conn.execute("""
                SELECT provider_name, provider_logo_path, monetization_type
                FROM streaming_availability
                WHERE tmdb_id = ? AND tmdb_type = ?
            """, (rec['recommended_tmdb_id'], rec['recommended_type'])).fetchall()

            provider_names = [p['provider_name'] for p in providers]
            for pn in provider_names:
                all_providers_set.add(pn)

            genres = []
            if rec['genres']:
                try:
                    genres = json.loads(rec['genres'])
                except (json.JSONDecodeError, TypeError):
                    pass
            for g in genres:
                all_genres_set.add(g)

            rec_dict = {
                'id': rec['id'],
                'recommended_title': rec['recommended_title'],
                'recommended_type': rec['recommended_type'],
                'recommended_tmdb_id': rec['recommended_tmdb_id'],
                'poster_path': rec['poster_path'],
                'source_title': rec['source_title'],
                'source_tag': rec['source_tag'] or 'both',
                'providers': providers,
                'provider_names': provider_names,
                'genres': genres,
                'first_genre': genres[0] if genres else 'Other',
                'collection_name': rec['collection_name'],
                'overview': rec['rec_overview'] or '',
                'backdrop_path': rec['rec_backdrop'] or '',
                'release_year': rec['rec_year'] or '',
                'vote_average': rec['vote_avg'] or 0,
                'match_score': rec['match_score'] or 0,
            }

            if rec['collection_name']:
                franchise_catchup[rec['collection_name']].append(rec_dict)
            elif rec['recommended_type'] == 'movie':
                movie_recs.append(rec_dict)
            else:
                tv_recs.append(rec_dict)

        # Group by genre — each rec appears in its first genre only
        def group_by_genre(recs, min_per_genre, max_genres):
            genre_groups = defaultdict(list)
            for r in recs:
                genre_groups[r['first_genre']].append(r)
            # Sort genres by count descending, filter by minimum
            sorted_genres = sorted(genre_groups.items(), key=lambda x: -len(x[1]))
            return [(g, items) for g, items in sorted_genres
                    if len(items) >= min_per_genre][:max_genres]

        movie_genre_rows = group_by_genre(movie_recs, 1, 8)
        tv_genre_rows = group_by_genre(tv_recs, 1, 5)

        # Hero items: top 3 recs with backdrop_path
        all_recs = movie_recs + tv_recs
        hero_items = [r for r in all_recs if r.get('backdrop_path')][:3]

        return render_template('watch_next.html',
                               hero_items=hero_items,
                               continue_watching=continue_watching,
                               franchise_catchup=dict(franchise_catchup),
                               movie_genre_rows=movie_genre_rows,
                               tv_genre_rows=tv_genre_rows,
                               all_providers=sorted(all_providers_set),
                               all_genres=sorted(all_genres_set),
                               review_count=get_review_count())
    finally:
        conn.close()


@app.route('/coming-soon')
def coming_soon():
    conn = get_db()
    try:
        tag_sql, tag_params = tag_filter_sql('t')
        from datetime import date as date_cls

        # TV: unwatched seasons with future/unknown air dates
        alerts_rows = conn.execute("""
            SELECT t.id, CASE WHEN t.original_language = 'he' THEN COALESCE(t.title_he, t.title_en) ELSE COALESCE(t.title_en, t.title_he) END AS title,
                   t.poster_path, t.tmdb_id, t.tmdb_type, t.user_tag,
                   t.vote_average, t.overview, t.backdrop_path, t.release_year,
                   st.max_watched_season, st.total_seasons_tmdb,
                   st.next_season_air_date, st.returning_series
            FROM series_tracking st
            JOIN titles t ON st.title_id = t.id
            WHERE st.status = ? AND (
                (st.total_seasons_tmdb > st.max_watched_season
                 AND (st.next_season_air_date IS NULL OR st.next_season_air_date > date('now')))
                OR (st.returning_series = 1
                    AND st.total_seasons_tmdb <= st.max_watched_season)
            )""" + tag_sql + """
            ORDER BY st.next_season_air_date ASC
        """, ('watching',) + tag_params).fetchall()

        tv_alerts = []
        for row in alerts_rows:
            providers = conn.execute("""
                SELECT provider_name, provider_logo_path, monetization_type
                FROM streaming_availability
                WHERE tmdb_id = ? AND tmdb_type = ?
            """, (row['tmdb_id'], row['tmdb_type'])).fetchall()

            is_returning = row['returning_series'] and (row['total_seasons_tmdb'] or 0) <= (row['max_watched_season'] or 0)

            if is_returning:
                new_season = (row['max_watched_season'] or 0) + 1
            else:
                new_season = (row['max_watched_season'] or 0) + 1

            air_date_display = None
            days_until = None
            if row['next_season_air_date']:
                try:
                    ad = datetime.strptime(row['next_season_air_date'], '%Y-%m-%d')
                    air_date_display = ad.strftime('%b %d, %Y')
                    days_until = (ad.date() - date_cls.today()).days
                except (ValueError, TypeError):
                    pass

            tv_alerts.append({
                'title': row['title'],
                'poster_path': row['poster_path'],
                'tmdb_id': row['tmdb_id'],
                'tmdb_type': row['tmdb_type'],
                'new_season': new_season,
                'watched_season': row['max_watched_season'] or 0,
                'total_seasons': row['total_seasons_tmdb'] or 0,
                'user_tag': row['user_tag'] or 'both',
                'providers': providers,
                'air_date': air_date_display,
                'days_until': days_until,
                'is_returning': is_returning,
                'vote_average': row['vote_average'] or 0,
                'overview': row['overview'] or '',
                'backdrop_path': row['backdrop_path'] or '',
                'release_year': row['release_year'] or '',
            })

        # Movie franchises — unreleased parts
        franchise_alerts = conn.execute("""
            SELECT collection_name, next_unreleased_title, next_unreleased_poster,
                   next_release_date, watched_parts, total_parts
            FROM franchise_tracking
            WHERE next_unreleased_tmdb_id IS NOT NULL
            ORDER BY next_release_date ASC
        """).fetchall()

        franchise_list = []
        for row in franchise_alerts:
            air_date_display = None
            days_until = None
            if row['next_release_date']:
                try:
                    ad = datetime.strptime(row['next_release_date'], '%Y-%m-%d')
                    air_date_display = ad.strftime('%b %d, %Y')
                    days_until = (ad.date() - date_cls.today()).days
                except (ValueError, TypeError):
                    pass
            franchise_list.append({
                'collection_name': row['collection_name'],
                'title': row['next_unreleased_title'],
                'poster_path': row['next_unreleased_poster'],
                'watched_parts': row['watched_parts'],
                'total_parts': row['total_parts'],
                'air_date': air_date_display,
                'days_until': days_until,
            })

        # Group all items by month for timeline view
        from collections import OrderedDict
        timeline = OrderedDict()
        all_items = []
        for a in tv_alerts:
            a['item_type'] = 'tv'
            all_items.append(a)
        for a in franchise_list:
            a['item_type'] = 'movie'
            all_items.append(a)

        # Sort by air_date (None/TBA last)
        def sort_key(item):
            if item.get('days_until') is not None:
                return (0, item['days_until'])
            return (1, 0)
        all_items.sort(key=sort_key)

        for item in all_items:
            if item.get('air_date'):
                try:
                    month_key = datetime.strptime(item['air_date'], '%b %d, %Y').strftime('%B %Y')
                except (ValueError, TypeError):
                    month_key = 'TBA'
            else:
                month_key = 'TBA'
            if month_key not in timeline:
                timeline[month_key] = []
            timeline[month_key].append(item)

        return render_template('coming_soon.html',
                               tv_alerts=tv_alerts,
                               franchise_alerts=franchise_list,
                               timeline=timeline,
                               review_count=get_review_count())
    finally:
        conn.close()


@app.route('/library')
def library():
    conn = get_db()
    try:
        tag_sql, tag_params = tag_filter_sql('t')
        titles = conn.execute("""
            SELECT t.id, t.title_he, t.title_en, t.original_language, t.tmdb_type, t.poster_path,
                   t.user_tag, t.vote_average, t.release_year, t.tmdb_id, t.genres,
                   t.overview, t.backdrop_path,
                   COUNT(wh.id) AS watch_count,
                   MAX(wh.watch_date) AS last_watched,
                   st.max_watched_season, st.total_seasons_tmdb, st.total_episodes_tmdb
            FROM titles t
            LEFT JOIN watch_history wh ON t.id = wh.title_id
            LEFT JOIN series_tracking st ON t.id = st.title_id
            WHERE 1=1""" + tag_sql + """
            GROUP BY t.id
            ORDER BY last_watched DESC
        """, tag_params).fetchall()

        # Compute library stats
        total_count = len(titles)
        movie_count = sum(1 for t in titles if t['tmdb_type'] == 'movie')
        tv_count = sum(1 for t in titles if t['tmdb_type'] == 'tv')
        dates = [t['last_watched'] for t in titles if t['last_watched']]
        earliest_year = min(dates)[:4] if dates else None
        stats = {
            'total': total_count,
            'movies': movie_count,
            'tv': tv_count,
            'since': earliest_year,
        }

        return render_template('library.html',
                               titles=titles,
                               stats=stats,
                               review_count=get_review_count())
    finally:
        conn.close()


@app.route('/review')
def review():
    conn = get_db()
    try:
        tag_sql, tag_params = tag_filter_sql('t')
        review_items = conn.execute("""
            SELECT t.id, t.tmdb_id, t.tmdb_type, t.title_he, t.title_en, t.original_language,
                   t.poster_path, t.confidence, t.user_tag,
                   wh.raw_csv_title AS raw_title
            FROM titles t
            LEFT JOIN watch_history wh ON t.id = wh.title_id
            WHERE t.match_status = ?""" + tag_sql + """
            GROUP BY t.id
            ORDER BY t.confidence DESC
        """, ('review',) + tag_params).fetchall()

        return render_template('review.html',
                               review_items=review_items,
                               review_count=len(review_items))
    finally:
        conn.close()


@app.route('/bulk-accept', methods=['POST'])
def bulk_accept():
    threshold = request.form.get('threshold', type=int)
    if threshold is None or threshold < 0 or threshold > 100:
        threshold = 45
    threshold_decimal = threshold / 100.0
    conn = get_db()
    try:
        cursor = conn.execute(
            "UPDATE titles SET match_status = 'auto' "
            "WHERE match_status = 'review' AND confidence >= ?",
            (threshold_decimal,)
        )
        conn.commit()
        count = cursor.rowcount
        flash(f'Accepted {count} titles with confidence >= {threshold}%.')
    finally:
        conn.close()
    return redirect(url_for('review'))


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
            purge_library_recommendations(conn)
        except Exception as e:
            logger.warning(f"Recommendation generation failed: {e}")
            rec_count = 0

        # Update last upload timestamp
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ('last_upload_date', datetime.now().isoformat())
        )
        conn.commit()

        new_titles = stats.get('matched', 0) + stats.get('review', 0)
        skipped = stats.get('skipped', 0)
        new_eps = stats.get('new_episodes', 0)
        flash(f"Upload complete: {new_titles} new titles, "
              f"{skipped} already in library, "
              f"{new_eps} new episodes added, "
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

    original_language = (details_en or details_he or {}).get('original_language')
    # Extract genres from TMDB detail response
    detail_data = details_he or details_en or {}
    genres_list = [g['name'] for g in detail_data.get('genres', [])]
    genres_json = json.dumps(genres_list) if genres_list else None
    overview = detail_data.get('overview')
    backdrop_path = detail_data.get('backdrop_path')
    vote_average = detail_data.get('vote_average')
    rel_date = detail_data.get('release_date') or detail_data.get('first_air_date') or ''
    release_year = rel_date[:4] if rel_date else None

    conn = get_db()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO titles
            (tmdb_id, tmdb_type, title_he, title_en, poster_path, original_language,
             match_status, confidence, source, user_tag, genres,
             overview, backdrop_path, vote_average, release_year)
            VALUES (?, ?, ?, ?, ?, ?, 'manual', 1.0, 'manual', ?, ?, ?, ?, ?, ?)
        """, (
            tmdb_id, tmdb_type,
            (details_he or {}).get('title') or (details_he or {}).get('name'),
            (details_en or {}).get('title') or (details_en or {}).get('name'),
            (details_he or details_en or {}).get('poster_path'),
            original_language,
            user_tag,
            genres_json,
            overview, backdrop_path, vote_average, release_year,
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
            next_season = watched_seasons + 1
            next_air_date = None
            if next_season <= num_seasons:
                for s in (details_en or {}).get('seasons', []):
                    if s.get('season_number') == next_season:
                        next_air_date = s.get('air_date')
                        break
            total_episodes = (details_en or details_he or {}).get('number_of_episodes')
            conn.execute("""
                INSERT OR REPLACE INTO series_tracking
                (title_id, tmdb_id, max_watched_season, total_seasons_tmdb,
                 next_season_air_date, total_episodes_tmdb, status)
                VALUES (?, ?, ?, ?, ?, ?, 'watching')
            """, (title_id, tmdb_id, watched_seasons, num_seasons,
                  next_air_date, total_episodes))

        conn.commit()

        # Generate recommendations for this title
        try:
            generate_recommendations(conn, tmdb_id, tmdb_type, title_id)
            purge_library_recommendations(conn)
            score_all_recommendations(conn)
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
    if request.headers.get('Accept') == 'application/json':
        return jsonify({'ok': True})
    return redirect(url_for('watch_next'))


@app.route('/undismiss/<int:rec_id>', methods=['POST'])
def undismiss(rec_id):
    conn = get_db()
    try:
        conn.execute(
            "UPDATE recommendations SET status = 'unseen' WHERE id = ?",
            (rec_id,)
        )
        conn.commit()
    finally:
        conn.close()
    if request.headers.get('Accept') == 'application/json':
        return jsonify({'ok': True})
    return redirect(url_for('watch_next'))


@app.route('/api/mark-watched/<int:rec_id>', methods=['POST'])
def mark_watched(rec_id):
    conn = get_db()
    try:
        conn.execute(
            "UPDATE recommendations SET status = 'watched' WHERE id = ?",
            (rec_id,)
        )
        conn.commit()
    finally:
        conn.close()
    return jsonify({'ok': True})


@app.route('/api/tag/<int:title_id>', methods=['POST'])
def change_tag(title_id):
    new_tag = request.form.get('user_tag', '')
    if new_tag not in ('me', 'wife', 'both'):
        return jsonify({'ok': False, 'error': 'invalid tag'}), 400
    conn = get_db()
    try:
        conn.execute(
            "UPDATE titles SET user_tag = ? WHERE id = ?",
            (new_tag, title_id)
        )
        conn.commit()
    finally:
        conn.close()
    return jsonify({'ok': True})


@app.route('/api/detail/<tmdb_type>/<int:tmdb_id>')
def api_detail(tmdb_type, tmdb_id):
    if tmdb_type not in ('movie', 'tv'):
        return jsonify({'error': 'invalid type'}), 400

    result = {'cast': [], 'director': None, 'trailer_key': None, 'similar': []}

    # Credits
    credits = tmdb_get(f'/{tmdb_type}/{tmdb_id}/credits', {'language': 'en-US'})
    if credits:
        result['cast'] = [
            {'name': c.get('name', ''), 'profile_path': c.get('profile_path')}
            for c in credits.get('cast', [])[:8]
        ]
        for crew in credits.get('crew', []):
            if crew.get('job') == 'Director':
                result['director'] = crew.get('name')
                break

    # Videos (trailer)
    videos = tmdb_get(f'/{tmdb_type}/{tmdb_id}/videos', {'language': 'en-US'})
    if videos:
        for v in videos.get('results', []):
            if v.get('site') == 'YouTube' and v.get('type') in ('Trailer', 'Teaser'):
                result['trailer_key'] = v.get('key')
                break

    # Similar
    similar = tmdb_get(f'/{tmdb_type}/{tmdb_id}/similar', {'language': 'en-US'})
    if similar:
        result['similar'] = [
            {
                'id': s['id'],
                'title': s.get('title') or s.get('name', ''),
                'name': s.get('name') or s.get('title', ''),
                'poster_path': s.get('poster_path'),
                'backdrop_path': s.get('backdrop_path'),
                'overview': (s.get('overview') or '')[:200],
                'vote_average': s.get('vote_average', 0),
                'media_type': s.get('media_type', tmdb_type),
                'release_date': s.get('release_date', ''),
                'first_air_date': s.get('first_air_date', ''),
            }
            for s in similar.get('results', [])[:6]
            if s.get('poster_path')
        ]

    return jsonify(result)


@app.route('/api/taste-profile')
def api_taste_profile():
    conn = get_db()
    try:
        # Genre distribution
        rows = conn.execute("SELECT genres FROM titles WHERE genres IS NOT NULL").fetchall()
        genre_counts = defaultdict(int)
        for row in rows:
            try:
                for g in json.loads(row['genres']):
                    genre_counts[g] += 1
            except (json.JSONDecodeError, TypeError):
                pass

        # Type split
        type_rows = conn.execute(
            "SELECT tmdb_type, COUNT(*) as cnt FROM titles GROUP BY tmdb_type"
        ).fetchall()
        type_split = {r['tmdb_type']: r['cnt'] for r in type_rows}

        # Average rating
        avg_row = conn.execute(
            "SELECT AVG(vote_average) as avg_rating FROM titles WHERE vote_average IS NOT NULL"
        ).fetchone()
        avg_rating = round(avg_row['avg_rating'], 1) if avg_row and avg_row['avg_rating'] else None

        # Decade distribution
        decade_rows = conn.execute(
            "SELECT SUBSTR(release_year, 1, 3) || '0s' as decade, COUNT(*) as cnt "
            "FROM titles WHERE release_year IS NOT NULL "
            "GROUP BY decade ORDER BY decade"
        ).fetchall()
        decades = {r['decade']: r['cnt'] for r in decade_rows}

        return jsonify({
            'genres': dict(sorted(genre_counts.items(), key=lambda x: -x[1])),
            'type_split': type_split,
            'avg_rating': avg_rating,
            'decades': decades,
        })
    finally:
        conn.close()


@app.route('/delete/<int:title_id>', methods=['POST'])
def delete_title(title_id):
    conn = get_db()
    try:
        title = conn.execute(
            "SELECT CASE WHEN original_language = 'he' THEN COALESCE(title_he, title_en) ELSE COALESCE(title_en, title_he) END AS name, tmdb_id, tmdb_type FROM titles WHERE id = ?",
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
        # Clean up franchise_tracking — remove this title from source_title_ids
        franchise_rows = conn.execute(
            "SELECT id, source_title_ids, watched_parts FROM franchise_tracking"
        ).fetchall()
        for fr in franchise_rows:
            ids = [x.strip() for x in (fr['source_title_ids'] or '').split(',') if x.strip()]
            if str(title_id) in ids:
                ids.remove(str(title_id))
                if ids:
                    conn.execute(
                        "UPDATE franchise_tracking SET source_title_ids = ?, watched_parts = MAX(0, watched_parts - 1) WHERE id = ?",
                        (','.join(ids), fr['id'])
                    )
                else:
                    conn.execute("DELETE FROM franchise_tracking WHERE id = ?", (fr['id'],))
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
            SELECT t.id, t.tmdb_id, t.tmdb_type, t.title_he, t.title_en, t.original_language, t.poster_path,
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
                       poster_path = ?, original_language = ?, match_status = 'manual', confidence = 1.0
                WHERE id = ?
            """, (
                new_tmdb_id, new_tmdb_type,
                (details_he or {}).get('title') or (details_he or {}).get('name'),
                (details_en or {}).get('title') or (details_en or {}).get('name'),
                (details_he or details_en or {}).get('poster_path'),
                (details_en or details_he or {}).get('original_language'),
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
            row = conn.execute(
                "SELECT tmdb_id, total_seasons_tmdb FROM series_tracking WHERE title_id = ?",
                (title_id,)
            ).fetchone()
            next_air_date = None
            if row:
                next_season = watched_seasons + 1
                if next_season <= (row['total_seasons_tmdb'] or 0):
                    detail = tmdb_get(f"/tv/{row['tmdb_id']}", {"language": "en-US"})
                    if detail:
                        for s in detail.get('seasons', []):
                            if s.get('season_number') == next_season:
                                next_air_date = s.get('air_date')
                                break
            conn.execute(
                "UPDATE series_tracking SET max_watched_season = ?, next_season_air_date = ? WHERE title_id = ?",
                (watched_seasons, next_air_date, title_id)
            )

        conn.commit()
        flash('Title updated.')
    finally:
        conn.close()
    return redirect(url_for('library'))


@app.route('/delete-all', methods=['POST'])
def delete_all():
    conn = get_db()
    try:
        conn.execute("DELETE FROM watch_history")
        conn.execute("DELETE FROM series_tracking")
        conn.execute("DELETE FROM recommendations")
        conn.execute("DELETE FROM streaming_availability")
        conn.execute("DELETE FROM franchise_tracking")
        conn.execute("DELETE FROM titles")
        conn.execute("DELETE FROM settings WHERE key = ?", ('last_upload_date',))
        conn.commit()
        flash('Library cleared. You can now upload a fresh CSV.')
    finally:
        conn.close()
    return redirect(url_for('library'))


if __name__ == '__main__':
    app.run(debug=True, port=5000)
