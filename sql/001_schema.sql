-- PharmacieDeGarde24.fr - Base Schema
-- PostgreSQL 16

CREATE TABLE IF NOT EXISTS departements (
  code VARCHAR(5) PRIMARY KEY,
  nom VARCHAR(100) NOT NULL,
  slug VARCHAR(120) NOT NULL UNIQUE,
  region VARCHAR(100),
  chef_lieu VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_departements_slug ON departements(slug);

CREATE TABLE IF NOT EXISTS communes (
  insee_code VARCHAR(10) PRIMARY KEY,
  nom VARCHAR(255) NOT NULL,
  slug VARCHAR(255) NOT NULL,
  departement_code VARCHAR(5) NOT NULL REFERENCES departements(code),
  postal_codes TEXT[] NOT NULL DEFAULT '{}',
  lat NUMERIC(9,6),
  lon NUMERIC(9,6),
  population INT DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_communes_dept ON communes(departement_code);
CREATE INDEX IF NOT EXISTS idx_communes_slug ON communes(slug);
CREATE INDEX IF NOT EXISTS idx_communes_postal ON communes USING gin(postal_codes);

CREATE TABLE IF NOT EXISTS pharmacies (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  finess_id VARCHAR(20) UNIQUE NOT NULL,
  nom VARCHAR(255) NOT NULL,
  slug VARCHAR(255) NOT NULL,
  adresse TEXT,
  code_postal VARCHAR(10) NOT NULL,
  ville VARCHAR(255) NOT NULL,
  departement_code VARCHAR(5) NOT NULL REFERENCES departements(code),
  insee_code VARCHAR(10),
  lat NUMERIC(9,6),
  lon NUMERIC(9,6),
  telephone VARCHAR(30),
  horaires JSONB DEFAULT '[]'::jsonb,
  is_open_24h BOOLEAN DEFAULT FALSE,
  is_garde_permanente BOOLEAN DEFAULT FALSE,
  source VARCHAR(50) DEFAULT 'FINESS',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pharmacies_dept ON pharmacies(departement_code);
CREATE INDEX IF NOT EXISTS idx_pharmacies_cp ON pharmacies(code_postal);
CREATE INDEX IF NOT EXISTS idx_pharmacies_slug ON pharmacies(slug);
CREATE INDEX IF NOT EXISTS idx_pharmacies_finess ON pharmacies(finess_id);
CREATE INDEX IF NOT EXISTS idx_pharmacies_coords ON pharmacies(lat, lon);

CREATE TABLE IF NOT EXISTS garde_shifts (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  pharmacy_id UUID NOT NULL REFERENCES pharmacies(id) ON DELETE CASCADE,
  type_garde VARCHAR(20) NOT NULL, -- 'nuit', 'dimanche', 'jour_ferie', '24h'
  date_debut TIMESTAMPTZ NOT NULL,
  date_fin TIMESTAMPTZ NOT NULL,
  secteur VARCHAR(100),
  source VARCHAR(100),
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_garde_shifts_dates ON garde_shifts(date_debut, date_fin);
CREATE INDEX IF NOT EXISTS idx_garde_shifts_pharmacy ON garde_shifts(pharmacy_id);
