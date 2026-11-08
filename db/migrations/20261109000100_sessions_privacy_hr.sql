-- migrate:up
-- B2: sign-in sessions, privacy-notice acceptance, and the HR fields the nightly import keeps (§3.1, §6.2).

ALTER TABLE users
  ADD COLUMN source             text        NOT NULL DEFAULT 'hr' CHECK (source IN ('hr', 'sign_in')),
  ADD COLUMN hr_department      text,                 -- as HR sends it, so mapping can be re-run when taxonomy changes
  ADD COLUMN hr_job_title       text,
  ADD COLUMN last_seen_in_hr_at timestamptz,
  ADD COLUMN last_sign_in_at    timestamptz;

-- Server-side sessions. The cookie holds a random token; only its SHA-256 is stored.
CREATE TABLE sessions (
  id_hash      bytea       PRIMARY KEY,
  user_id      uuid        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  created_at   timestamptz NOT NULL DEFAULT now(),
  last_seen_at timestamptz NOT NULL DEFAULT now(),
  expires_at   timestamptz NOT NULL,
  revoked_at   timestamptz,
  CHECK (expires_at > created_at)
);
CREATE INDEX sessions_user ON sessions (user_id);
CREATE INDEX sessions_expiry ON sessions (expires_at) WHERE revoked_at IS NULL;

-- One row per person per notice version they accepted (§6.2: "stored with the notice version").
CREATE TABLE privacy_acceptances (
  user_id        uuid        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  notice_version text        NOT NULL,
  accepted_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, notice_version)
);

-- Open taxonomy proposals are looked up by kind and value on every HR import.
CREATE INDEX review_items_open_ref ON review_items (item_type, ref_id) WHERE state IN ('open', 'in_progress');

-- migrate:down
DROP INDEX IF EXISTS review_items_open_ref;
DROP TABLE IF EXISTS privacy_acceptances;
DROP TABLE IF EXISTS sessions;
ALTER TABLE users
  DROP COLUMN IF EXISTS last_sign_in_at,
  DROP COLUMN IF EXISTS last_seen_in_hr_at,
  DROP COLUMN IF EXISTS hr_job_title,
  DROP COLUMN IF EXISTS hr_department,
  DROP COLUMN IF EXISTS source;
