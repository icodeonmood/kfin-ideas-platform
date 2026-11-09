-- migrate:up
-- Solution write-ups other teams can adopt (BLD-133). The owner of a shipped or resolved delivery drafts it; the
-- named sponsor approves it (never the person who submitted it). Approval gives it a SOL- number and queues it for
-- the repo writer, which writes `solutions/SOL-NNNN.md`; the indexer then shows it as "Already running" and the
-- B5 adoption request flow works on it. The text is checked for personal data and for colleague and client names
-- before it is saved, and stored sealed until it is published.
CREATE TABLE solution_writeups (
  id              bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  delivery_id     bigint      NOT NULL UNIQUE REFERENCES deliveries (id) ON DELETE CASCADE,
  state           text        NOT NULL DEFAULT 'draft' CHECK (state IN ('draft', 'submitted', 'approved', 'sent_back')),
  parts_encrypted bytea       NOT NULL,
  drafted_by      uuid        NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
  submitted_by    uuid        REFERENCES users (id) ON DELETE RESTRICT,
  submitted_at    timestamptz,
  approved_by     uuid        REFERENCES users (id) ON DELETE RESTRICT,
  approved_at     timestamptz,
  solution_id     text        UNIQUE CHECK (solution_id ~ '^SOL-[0-9]{4}$'),
  repo_path       text,
  repo_commit     text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX solution_writeups_waiting ON solution_writeups (state) WHERE state = 'submitted';
CREATE TRIGGER solution_writeups_updated_at BEFORE UPDATE ON solution_writeups
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Publishing new solutions to everyone's matches can be paused (admin).
INSERT INTO kill_switches (name) VALUES ('solutions.publish') ON CONFLICT (name) DO NOTHING;

-- migrate:down
DELETE FROM kill_switches WHERE name = 'solutions.publish';
DROP TABLE IF EXISTS solution_writeups;
DELETE FROM id_counters WHERE kind = 'SOL';
