-- Phase 1: Add rich metadata columns for UI enrichment
-- These fields already exist in TMDB responses we currently discard

ALTER TABLE titles ADD COLUMN overview TEXT;
ALTER TABLE titles ADD COLUMN backdrop_path TEXT;
ALTER TABLE titles ADD COLUMN vote_average REAL;
ALTER TABLE titles ADD COLUMN release_year TEXT;

ALTER TABLE recommendations ADD COLUMN overview TEXT;
ALTER TABLE recommendations ADD COLUMN backdrop_path TEXT;
ALTER TABLE recommendations ADD COLUMN release_year TEXT;
-- recommendations.tmdb_recommendation_score already stores vote_average
