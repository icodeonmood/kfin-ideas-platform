-- migrate:up
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Keeps updated_at current on every UPDATE.
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END $$;

-- Guards append-only tables (points_ledger, audit_log).
CREATE OR REPLACE FUNCTION forbid_update_delete() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION '% is append-only', TG_TABLE_NAME USING ERRCODE = 'insufficient_privilege';
END $$;

-- Sequential numbers for coded IDs: SUB-/IDEA- share one counter per year (§2.3).
CREATE TABLE id_counters (
  kind       text    NOT NULL,
  period     text    NOT NULL,             -- '2026' for yearly IDs, '' for running ones (CL-, SOL-)
  last_value integer NOT NULL DEFAULT 0,
  PRIMARY KEY (kind, period)
);

CREATE OR REPLACE FUNCTION next_number(p_kind text, p_period text) RETURNS integer
LANGUAGE sql AS $$
  INSERT INTO id_counters (kind, period, last_value) VALUES (p_kind, p_period, 1)
  ON CONFLICT (kind, period) DO UPDATE SET last_value = id_counters.last_value + 1
  RETURNING last_value
$$;

-- migrate:down
DROP FUNCTION IF EXISTS next_number(text, text);
DROP TABLE IF EXISTS id_counters;
DROP FUNCTION IF EXISTS forbid_update_delete();
DROP FUNCTION IF EXISTS set_updated_at();
DROP EXTENSION IF EXISTS pgcrypto;
DROP EXTENSION IF EXISTS pg_trgm;
DROP EXTENSION IF EXISTS vector;
