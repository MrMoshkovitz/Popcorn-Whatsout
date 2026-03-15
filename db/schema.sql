CREATE TABLE IF NOT EXISTS titles (
    id INTEGER PRIMARY KEY,
    tmdb_id INTEGER NOT NULL,
    tmdb_type TEXT NOT NULL CHECK(tmdb_type IN ('movie', 'tv')),
    title_en TEXT,
    title_he TEXT,
    poster_path TEXT,
    original_language TEXT,
    confidence REAL DEFAULT 1.0,
    match_status TEXT DEFAULT 'auto' CHECK(match_status IN ('auto', 'review', 'manual')),
    source TEXT DEFAULT 'csv' CHECK(source IN ('csv', 'manual')),
    user_tag TEXT DEFAULT 'both' CHECK(user_tag IN ('me', 'wife', 'both')),
    genres TEXT,
    overview TEXT,
    backdrop_path TEXT,
    vote_average REAL,
    release_year TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tmdb_id, tmdb_type)
);

CREATE TABLE IF NOT EXISTS watch_history (
    id INTEGER PRIMARY KEY,
    title_id INTEGER REFERENCES titles(id),
    raw_csv_title TEXT,
    watch_date DATE NOT NULL,
    season_number INTEGER,
    episode_name TEXT,
    UNIQUE(title_id, watch_date, season_number, episode_name)
);

CREATE TABLE IF NOT EXISTS series_tracking (
    id INTEGER PRIMARY KEY,
    title_id INTEGER REFERENCES titles(id),
    tmdb_id INTEGER NOT NULL,
    total_seasons_tmdb INTEGER,
    max_watched_season INTEGER,
    last_checked TIMESTAMP,
    status TEXT DEFAULT 'watching' CHECK(status IN ('watching', 'completed', 'dropped')),
    next_season_air_date TEXT,
    total_episodes_tmdb INTEGER,
    returning_series INTEGER DEFAULT 0,
    UNIQUE(title_id)
);

CREATE TABLE IF NOT EXISTS recommendations (
    id INTEGER PRIMARY KEY,
    source_title_id INTEGER REFERENCES titles(id),
    recommended_tmdb_id INTEGER NOT NULL,
    recommended_type TEXT NOT NULL,
    recommended_title TEXT,
    poster_path TEXT,
    tmdb_recommendation_score REAL,
    collection_name TEXT,
    genres TEXT,
    overview TEXT,
    backdrop_path TEXT,
    release_year TEXT,
    status TEXT DEFAULT 'unseen' CHECK(status IN ('unseen', 'dismissed', 'watched')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_title_id, recommended_tmdb_id)
);

CREATE TABLE IF NOT EXISTS streaming_availability (
    id INTEGER PRIMARY KEY,
    tmdb_id INTEGER NOT NULL,
    tmdb_type TEXT NOT NULL,
    provider_name TEXT NOT NULL,
    provider_logo_path TEXT,
    monetization_type TEXT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tmdb_id, tmdb_type, provider_name, monetization_type)
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS franchise_tracking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_id INTEGER NOT NULL UNIQUE,
    collection_name TEXT,
    total_parts INTEGER,
    watched_parts INTEGER DEFAULT 0,
    next_unreleased_tmdb_id INTEGER,
    next_unreleased_title TEXT,
    next_unreleased_poster TEXT,
    next_release_date TEXT,
    last_checked TIMESTAMP,
    source_title_ids TEXT
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    filename TEXT PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_watch_history_title ON watch_history(title_id);
CREATE INDEX IF NOT EXISTS idx_series_tracking_status ON series_tracking(status);
CREATE INDEX IF NOT EXISTS idx_recommendations_status ON recommendations(status);
CREATE INDEX IF NOT EXISTS idx_streaming_tmdb ON streaming_availability(tmdb_id, tmdb_type);
CREATE INDEX IF NOT EXISTS idx_franchise_collection ON franchise_tracking(collection_id);
