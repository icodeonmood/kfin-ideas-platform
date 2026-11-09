-- migrate:up
-- Review fixes for the coming-soon features (BLD-141 to BLD-146).

-- 1. Everyone who drafted, edited or submitted a write-up; none of them may approve it (BLD-142).
ALTER TABLE solution_writeups ADD COLUMN contributors uuid[] NOT NULL DEFAULT '{}';
UPDATE solution_writeups SET contributors = array_remove(ARRAY[drafted_by, submitted_by], NULL);

-- 2. Events the repo writer can never commit (a hand-added file, personal data that slipped through) leave the head
--    of the queue: dead-lettered with their code, alerted, and retried only by hand (RUNBOOK §4.8) (BLD-143).
ALTER TABLE outbox ADD COLUMN dead_lettered_at timestamptz;
DROP INDEX IF EXISTS outbox_pending;
CREATE INDEX outbox_pending ON outbox (id) WHERE committed_at IS NULL AND dead_lettered_at IS NULL;

-- 3. Stage history, made safe for "picked this month" (BLD-145): backfilled rows learn the stage they came from,
--    and every idea gets a marker row for its stage today, so nothing already picked counts as newly picked.
WITH ordered AS (
  SELECT id, lag(to_stage) OVER (PARTITION BY idea_uuid ORDER BY at, id) AS prev
  FROM idea_stage_history WHERE source = 'backfill'
)
UPDATE idea_stage_history h SET from_stage = o.prev
FROM ordered o WHERE o.id = h.id AND h.from_stage IS NULL AND o.prev IS NOT NULL;
INSERT INTO idea_stage_history (idea_uuid, from_stage, to_stage, at, source)
SELECT id, stage, stage, now(), 'backfill' FROM ideas;

-- migrate:down
DELETE FROM idea_stage_history WHERE source = 'backfill' AND from_stage = to_stage;
DROP INDEX IF EXISTS outbox_pending;
CREATE INDEX outbox_pending ON outbox (id) WHERE committed_at IS NULL;
ALTER TABLE outbox DROP COLUMN IF EXISTS dead_lettered_at;
ALTER TABLE solution_writeups DROP COLUMN IF EXISTS contributors;
