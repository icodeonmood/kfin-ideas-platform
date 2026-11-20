-- migrate:up
-- A reviewer's queued questions are kept between visits (BLD-B272, amends BLD-B244; L-QUESTIONS/4, S-R2.panel). The
-- panel saves the whole queue after each change, and each save carries `base`, the revision its page last knew was
-- stored for that reviewer (0 when none). The worker keeps the save only when the stored revision is `base`, and then
-- stores `base + 1` here (compare-and-swap, BLD-B272's fix round with 20261122200500), so a stale tab's save, or one
-- that overtook a save its page never heard back from, never overwrites a newer queue. Only a queued set written by
-- a save has one; a sent set and every set from before this column have none (read as 0).
ALTER TABLE question_sets ADD COLUMN queue_rev bigint;
ALTER TABLE question_sets ADD CONSTRAINT question_sets_queue_rev_check CHECK (queue_rev IS NULL OR queue_rev > 0);

-- migrate:down
ALTER TABLE question_sets DROP CONSTRAINT IF EXISTS question_sets_queue_rev_check;
ALTER TABLE question_sets DROP COLUMN IF EXISTS queue_rev;
