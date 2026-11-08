-- migrate:up
-- One scan per submitted idea (§4.2 steps 3–4 on day one; matching joins in B5). The tagged agent outputs and
-- the person's override reason are encrypted: they carry idea text (BLD-074).
CREATE TABLE scans (
  idea_uuid                uuid        PRIMARY KEY REFERENCES ideas (id) ON DELETE CASCADE,
  state                    text        NOT NULL DEFAULT 'queued'
                             CHECK (state IN ('queued', 'running', 'waiting', 'done', 'manual')),
  step                     text        NOT NULL DEFAULT 'queued'
                             CHECK (step IN ('queued', 'gatekeeper', 'canvas_assist', 'matching', 'done')),
  outcome                  text        CHECK (outcome IN ('ready', 'blocked', 'redirect', 'held', 'redirected')),
  overrides                jsonb       NOT NULL DEFAULT '{}',   -- flags only: not_personal_data, is_an_idea
  override_reason_encrypted bytea,
  result_encrypted         bytea,      -- {"gatekeeper": …, "canvas_assist": …}, tagged
  attempts                 integer     NOT NULL DEFAULT 0,
  error_code               text        CHECK (error_code ~ '^[a-z0-9_.]{1,60}$'),
  duration_ms              integer,
  started_at               timestamptz,
  finished_at              timestamptz,
  created_at               timestamptz NOT NULL DEFAULT now(),
  updated_at               timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX scans_waiting ON scans (state) WHERE state IN ('waiting', 'manual');
CREATE TRIGGER scans_updated_at BEFORE UPDATE ON scans FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- migrate:down
DROP TABLE IF EXISTS scans;
