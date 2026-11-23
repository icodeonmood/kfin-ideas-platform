-- migrate:up
-- L-HIDE.detect, DEC-131 (3), BLD-B278 (lane B, on lane C's BLD-C231). Additive only. `gatekeeper_done_at` marks a text
-- the review desk wrote whose gatekeeper check is complete: a sent question, a decision reason, the committee's
-- reversal note, a desk merge's note and the reviewer's worth note. NULL means the text has had the patterns and names
-- only: written while the assistant (`ai.all`) or the gatekeeper (`agent.gatekeeper`) was off, or while the gateway
-- failed. Once both switches are on, lane C's watch queues lane B's `desk.text_recheck`, which asks the gatekeeper about
-- a few of these texts at a time and hides what it finds in every copy of the idea (`desk/text_recheck.py`). Every row
-- that exists today starts NULL, so each desk text written before this column is checked once at the first switch-on.
-- The web role keeps the grants it had (it never writes these columns).
ALTER TABLE questions ADD COLUMN gatekeeper_done_at timestamptz;
ALTER TABLE idea_decisions ADD COLUMN gatekeeper_done_at timestamptz;
ALTER TABLE decision_reversals ADD COLUMN gatekeeper_done_at timestamptz;
ALTER TABLE merges ADD COLUMN gatekeeper_done_at timestamptz;
ALTER TABLE idea_worth ADD COLUMN gatekeeper_done_at timestamptz;
-- The queue: only the rows the re-check reads (a desk merge's note, the reviewer's worth note with words in it)
CREATE INDEX questions_unchecked ON questions (created_at) WHERE gatekeeper_done_at IS NULL;
CREATE INDEX idea_decisions_unchecked ON idea_decisions (at) WHERE gatekeeper_done_at IS NULL;
CREATE INDEX decision_reversals_unchecked ON decision_reversals (at) WHERE gatekeeper_done_at IS NULL;
CREATE INDEX merges_unchecked ON merges (at)
  WHERE gatekeeper_done_at IS NULL AND via = 'review_desk' AND note_encrypted IS NOT NULL;
CREATE INDEX idea_worth_unchecked ON idea_worth (at)
  WHERE gatekeeper_done_at IS NULL AND by_side = 'reviewer' AND note_encrypted IS NOT NULL;

-- migrate:down
DROP INDEX IF EXISTS idea_worth_unchecked;
DROP INDEX IF EXISTS merges_unchecked;
DROP INDEX IF EXISTS decision_reversals_unchecked;
DROP INDEX IF EXISTS idea_decisions_unchecked;
DROP INDEX IF EXISTS questions_unchecked;
ALTER TABLE idea_worth DROP COLUMN IF EXISTS gatekeeper_done_at;
ALTER TABLE merges DROP COLUMN IF EXISTS gatekeeper_done_at;
ALTER TABLE decision_reversals DROP COLUMN IF EXISTS gatekeeper_done_at;
ALTER TABLE idea_decisions DROP COLUMN IF EXISTS gatekeeper_done_at;
ALTER TABLE questions DROP COLUMN IF EXISTS gatekeeper_done_at;
