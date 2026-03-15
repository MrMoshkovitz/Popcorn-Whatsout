-- Add genres to titles and recommendations, returning_series flag, franchise tracking table

ALTER TABLE titles ADD COLUMN genres TEXT;
ALTER TABLE recommendations ADD COLUMN collection_name TEXT;
ALTER TABLE recommendations ADD COLUMN genres TEXT;
ALTER TABLE series_tracking ADD COLUMN returning_series INTEGER DEFAULT 0;

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
CREATE INDEX IF NOT EXISTS idx_franchise_collection ON franchise_tracking(collection_id);
