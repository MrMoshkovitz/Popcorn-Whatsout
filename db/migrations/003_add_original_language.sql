ALTER TABLE titles ADD COLUMN original_language TEXT;

-- Fix title_he/title_en naming for existing CSV-imported titles.
-- The tmdb_matcher searched with he-IL, so result.get("title") returned Hebrew
-- but was stored as title_en, and result.get("original_title") returned the
-- original language title but was stored as title_he. Swap to correct this.
UPDATE titles SET title_he = title_en, title_en = title_he WHERE source = 'csv';
