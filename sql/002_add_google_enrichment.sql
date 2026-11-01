-- Migration: Add Google Places & Reviews Enrichment columns
ALTER TABLE pharmacies
  ADD COLUMN IF NOT EXISTS google_place_id VARCHAR(255),
  ADD COLUMN IF NOT EXISTS google_rating NUMERIC(3,2),
  ADD COLUMN IF NOT EXISTS google_user_ratings_total INT DEFAULT 0,
  ADD COLUMN IF NOT EXISTS google_reviews JSONB DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS google_photos TEXT[] DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS google_website TEXT,
  ADD COLUMN IF NOT EXISTS editorial_summary TEXT,
  ADD COLUMN IF NOT EXISTS google_opening_hours JSONB DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS enriched_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_pharmacies_rating ON pharmacies(google_rating);
CREATE INDEX IF NOT EXISTS idx_pharmacies_place_id ON pharmacies(google_place_id);
