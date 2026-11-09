-- migrate:up
-- Ember, email and points review fixes (BLD-134).
--
-- 1. The Ember's send is two-person and server-side: the core committee chair approves the note, which makes the
--    issue `ready` and issues a confirm token; an admin who neither wrote nor approved the note sends it with that
--    token. A note changed after approval takes the issue back to `draft`.
ALTER TABLE ember_issues DROP CONSTRAINT IF EXISTS ember_issues_state_check;
ALTER TABLE ember_issues
  ADD CONSTRAINT ember_issues_state_check CHECK (state IN ('draft', 'ready', 'sent')),
  ADD COLUMN note_approved_by uuid REFERENCES users (id) ON DELETE RESTRICT,
  ADD COLUMN note_approved_at timestamptz,
  ADD COLUMN ready_token      text;

-- 2. Every change of an idea's stage, with when it happened (milestone points are dated at the event; The Ember
--    counts ideas picked within the month). Kept by a trigger, so every path that moves a stage is recorded.
CREATE TABLE idea_stage_history (
  id          bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  idea_uuid   uuid        NOT NULL REFERENCES ideas (id) ON DELETE CASCADE,
  from_stage  text,
  to_stage    text        NOT NULL,
  at          timestamptz NOT NULL DEFAULT now(),
  source      text        NOT NULL DEFAULT 'live' CHECK (source IN ('live', 'backfill'))
);
CREATE INDEX idea_stage_history_idea ON idea_stage_history (idea_uuid, at);
CREATE INDEX idea_stage_history_to ON idea_stage_history (to_stage, at);

CREATE OR REPLACE FUNCTION record_idea_stage() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'INSERT' OR OLD.stage IS DISTINCT FROM NEW.stage THEN
    INSERT INTO idea_stage_history (idea_uuid, from_stage, to_stage)
    VALUES (NEW.id, CASE WHEN TG_OP = 'UPDATE' THEN OLD.stage END, NEW.stage);
  END IF;
  RETURN NULL;
END $$;
CREATE TRIGGER ideas_stage_history AFTER INSERT OR UPDATE OF stage ON ideas
  FOR EACH ROW EXECUTE FUNCTION record_idea_stage();

-- Backfill from what the outbox already recorded (the same events that wrote the ideas' history lines in the
-- company repo): stage changes with their time. Older moves stay unknown; code falls back to the sync time.
INSERT INTO idea_stage_history (idea_uuid, from_stage, to_stage, at, source)
SELECT i.id, NULL, o.payload -> 'history' -> 0 ->> 'event', o.created_at, 'backfill'
FROM outbox o JOIN ideas i ON i.idea_id = o.aggregate_id
WHERE o.event_type = 'idea.stage_changed'
  AND o.payload -> 'history' -> 0 ->> 'event' IN (
    'reviewed', 'in_cluster', 'ready_for_scoring', 'scored', 'shortlisted', 'presenting', 'picked', 'handover',
    'in_garage', 'in_fix_track', 'shipped', 'resolved', 'measuring', 'closed', 'parked', 'declined', 'withdrawn');

-- 3. The points ledger is truly append-only: TRUNCATE is refused too, and the app roles never had it.
CREATE TRIGGER points_ledger_no_truncate BEFORE TRUNCATE ON points_ledger
  FOR EACH STATEMENT EXECUTE FUNCTION forbid_update_delete();
REVOKE TRUNCATE ON points_ledger FROM ideas_worker_svc, ideas_web_svc;

-- migrate:down
DROP TRIGGER IF EXISTS points_ledger_no_truncate ON points_ledger;
DROP TRIGGER IF EXISTS ideas_stage_history ON ideas;
DROP FUNCTION IF EXISTS record_idea_stage();
DROP TABLE IF EXISTS idea_stage_history;
UPDATE ember_issues SET state = 'draft' WHERE state = 'ready';
ALTER TABLE ember_issues
  DROP COLUMN IF EXISTS ready_token,
  DROP COLUMN IF EXISTS note_approved_at,
  DROP COLUMN IF EXISTS note_approved_by,
  DROP CONSTRAINT IF EXISTS ember_issues_state_check;
ALTER TABLE ember_issues ADD CONSTRAINT ember_issues_state_check CHECK (state IN ('draft', 'sent'));
