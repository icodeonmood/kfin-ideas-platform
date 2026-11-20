-- migrate:up
-- A reviewer's queued questions are kept between visits (BLD-B272, amends BLD-B244; L-QUESTIONS/4, S-R2.panel). The
-- panel saves the whole queue after each change, and each save carries the panel's revision: a number that only grows
-- (the browser's clock in milliseconds, or one more than the last). The worker keeps the queued set only when a save's
-- revision is higher than the one stored for that reviewer, so a save that arrives late (an earlier one overtaken on
-- the network, or another tab's older queue) never overwrites a newer one. Only a queued set written by that save has
-- one; a sent set and every set from before this column have none (read as 0).
ALTER TABLE question_sets ADD COLUMN queue_rev bigint;
ALTER TABLE question_sets ADD CONSTRAINT question_sets_queue_rev_check CHECK (queue_rev IS NULL OR queue_rev > 0);

-- migrate:down
ALTER TABLE question_sets DROP CONSTRAINT IF EXISTS question_sets_queue_rev_check;
ALTER TABLE question_sets DROP COLUMN IF EXISTS queue_rev;
